"""

Differentially Private Image Classification With ResNet

Author: [Josh Messitte](https://joshmessitte.dev)

Date Created: 2/12/2022

Description: Training a ResNet to classify images from the CIFAR-10 dataset in an epsilon-differentially private manner using PyTorch and Opacus. 

**UGA CSCI 8960** 

Project Overview
This project will:


*   Identify & tune important parameters for ϵ-DP training.
*   Use Opacus to identify layers incompatible with ϵ-DP.
*   Train a ϵ-DP ResNet for CIFAR-10 image classification using RMSprop.
*   Maximize accuracy while maintaining privacy.

"""


# ignore warnings for clarity
import warnings
warnings.simplefilter("ignore")

"""
Tuning Hyper-parameters

The normal hyper-parameters for the model we will use are:

*   Step Size: AKA learning rate. Amount the weights are updated during model training.


"""

STEP_SIZE = 1e-3

# Also need to specify number of epochs and batch size
EPOCHS = 20
BATCH_SIZE = 200
MAX_PHYSICAL_BATCH_SIZE = 128

"""
And the following privacy-specific hyper-parameters:
*   Clipping Threshold: The maximum L2 norm (sum of squared values) to which per sample gradients are clipped.
*   Epsilon: The target (maximum) epsilon to use when training and testing the model.
*   Delta: The targer δ for our ϵ-DP guarantee. This is the probability of any information accidentally being leaked. Set to 1e-5.
"""

CLIPPING_THRESHOLD = 1.2
EPSILON = 5
DELTA = 1e-5

"""
Loading the Data
Here we are loading the CIFAR-10 dataset. No data augmentation is utilized as some prior works suggest that models trained using data augmentation may underestimate the resulting risk of a privacy attack (Yu,2021).
"""

import torch
import torchvision
import torchvision.transforms as transforms

# These values are specific to the CIFAR-10 dataset
CIFAR10_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR10_STD_DEV = (0.2023, 0.1994, 0.2010)

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(CIFAR10_MEAN, CIFAR10_STD_DEV),
])

"""Then we can load the images and convert the PILImages to data of type Tensor."""

from torchvision.datasets import CIFAR10

DATA_ROOT = '../cifar10'

train_dataset = CIFAR10(
    root=DATA_ROOT, train=True, download=True, transform=transform)

train_loader = torch.utils.data.DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
)

test_dataset = CIFAR10(
    root=DATA_ROOT, train=False, download=True, transform=transform)

test_loader = torch.utils.data.DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
)

"""
Model

Now we will create our ResNet model using the torchvision package. We will be using a ResNet18 which specifies 18 layers in the network.
"""

from torchvision import models

model = models.resnet18(num_classes=10)

"""
Identifying Incompatible Layers

Some layers are not compatible with Opacus due to privacy implications. For example, we discussed in class how BatchNorm layers cannot be used because ϵ-DP relies upon using only neighboring datasets.
"""

# if opacus is not installed, it can be installed by specifying a command line statement: 
#!pip3 install opacus

from opacus.validators import ModuleValidator

errors = ModuleValidator.validate(model, strict=False)
errors[-5:]

"""We can remove incompatible layers using ModuleValidator.fix()"""

model = ModuleValidator.fix(model)
ModuleValidator.validate(model,strict=False)

"""
Utilizing GPUs

SaturnCloud supports GPUs, so we can specify our device to be CUDA-compatible.


"""

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = model.to(device)

"""
Optimization Method & Loss Criterion

We can specify our loss criterion (Cross Entropy Loss) and our optimization method (RMSprop):
"""

import torch.nn as nn
import torch.optim as optim

criterion = nn.CrossEntropyLoss()
optimizer = optim.RMSprop(model.parameters(), lr=STEP_SIZE)

"""
Privacy Engine

We now take our privacy-specific hyper-parameters and attach them to the privacy engine provided by Opacus.
"""

from opacus import PrivacyEngine

privacy_engine = PrivacyEngine()

model, optimizer, train_loader = privacy_engine.make_private_with_epsilon(
    module=model,
    optimizer=optimizer,
    data_loader=train_loader,
    epochs=EPOCHS,
    target_epsilon=EPSILON,
    target_delta=DELTA,
    max_grad_norm=CLIPPING_THRESHOLD,
)

print(f"Using sigma={optimizer.noise_multiplier} and C={CLIPPING_THRESHOLD}")

"""
Accuracy Calculator

This method will measure the accuracy of our model (training $ testing).
"""

def accuracy(preds, labels):
    return (preds == labels).mean()

"""
Training Function

This function trains the model for one epoch.
"""

from numpy.lib.function_base import append
import numpy as np
from opacus.utils.batch_memory_manager import BatchMemoryManager


def train(model, train_loader, optimizer, epoch, device):
    model.train()
    criterion = nn.CrossEntropyLoss()

    losses = []
    top1_acc = []
    passed = []
    
    with BatchMemoryManager(
        data_loader=train_loader, 
        max_physical_batch_size=MAX_PHYSICAL_BATCH_SIZE, 
        optimizer=optimizer
    ) as memory_safe_data_loader:

        for i, (images, target) in enumerate(memory_safe_data_loader):   
            
            optimizer.zero_grad()
            images = images.to(device)
            target = target.to(device)

            # compute output
            output = model(images)
            loss = criterion(output, target)

            preds = np.argmax(output.detach().cpu().numpy(), axis=1)
            labels = target.detach().cpu().numpy()

            # measure accuracy and record loss
            acc = accuracy(preds, labels)

            losses.append(loss.item())
            top1_acc.append(acc)

            loss.backward()
            optimizer.step()

            if (i+1) % 200 == 0 and epoch not in passed:
                epsilon = privacy_engine.get_epsilon(DELTA)
                passed.append(epoch)
                print(
                    f"\tTrain Epoch: {epoch} \t"
                    f"Loss: {np.mean(losses):.6f} "
                    f"Acc@1: {np.mean(top1_acc) * 100:.6f} "
                    f"(ε = {epsilon:.2f}, δ = {DELTA})"
                )

"""
Test Function

Our test function will validate our model on the 10k large test dataset.
"""

def test(model, test_loader, device):
    model.eval()
    criterion = nn.CrossEntropyLoss()
    losses = []
    top1_acc = []

    with torch.no_grad():
        for images, target in test_loader:
            images = images.to(device)
            target = target.to(device)

            output = model(images)
            loss = criterion(output, target)
            preds = np.argmax(output.detach().cpu().numpy(), axis=1)
            labels = target.detach().cpu().numpy()
            acc = accuracy(preds, labels)

            losses.append(loss.item())
            top1_acc.append(acc)

    top1_avg = np.mean(top1_acc)

    print(
        f"\tTest set:"
        f"Loss: {np.mean(losses):.6f} "
        f"Acc: {top1_avg * 100:.6f} "
    )
    return np.mean(top1_acc)

"""
Train the ResNet
"""

from tqdm.notebook import tqdm

for epoch in tqdm(range(EPOCHS), desc="Epoch", unit="epoch"):
    train(model, train_loader, optimizer, epoch + 1, device)

"""
Test the ResNet on Test Data
"""

top1_acc = test(model, test_loader, device)

"""## References
*   Yu, D., Zhang, H., Chen, W., Yin, J., & Liu, T.-Y. (2021). How Does Data Augmentation Affect Privacy in Machine Learning? arXiv [cs.LG]. Opgehaal van http://arxiv.org/abs/2007.10567
*   He, K., Zhang, X., Ren, S., & Sun, J. (2015). Deep Residual Learning for Image Recognition. arXiv [cs.CV]. Opgehaal van http://arxiv.org/abs/1512.03385


"""