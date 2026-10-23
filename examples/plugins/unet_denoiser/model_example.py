"""Export a tiny U-Net for an interface test; random weights are NOT a denoiser."""

import argparse
import torch
from torch import nn


class TinyUNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = nn.Sequential(
            nn.Conv2d(1, 8, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(8, 8, 3, padding=1),
            nn.ReLU(),
        )
        self.pool = nn.AvgPool2d(2)
        self.mid = nn.Sequential(nn.Conv2d(8, 16, 3, padding=1), nn.ReLU())
        self.up = nn.ConvTranspose2d(16, 8, 2, stride=2)
        self.out = nn.Conv2d(16, 1, 1)

    def forward(self, x):
        skip = self.enc(x)
        b = self.up(self.mid(self.pool(skip)))
        return torch.sigmoid(self.out(torch.cat((skip, b), dim=1)))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output")
    args = p.parse_args()
    torch.manual_seed(7)
    torch.jit.script(TinyUNet().eval()).save(args.output)
    print(
        "Interface-test checkpoint only. Train a model before using it for denoising."
    )
