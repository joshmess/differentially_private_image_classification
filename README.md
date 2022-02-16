# differentially_private_image_classification
Training a private ResNet to classify images from the CIFAR-10 dataset using PyTorch's Opacus.
UGA CSCI 8960


## ResNet Model

### Different Privacy Levels

```bash
Target Epsilon: 50 | Delta: 1e-5 | Clipping Threshold: 1.2 | Step Size: 1e-3 | Test Set Loss: 1.743414 | Test Accuracy: 60.087316 |
```

```bash
Target Epsilon: 10 | Delta: 1e-5 | Clipping Threshold: 1.2 | Step Size: 1e-3 | Test Set Loss: 1.775980 | Test Accuracy: 55.926585 | 
```
