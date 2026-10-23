# Third party references and distribution notices

SAM Image Studio application code is distributed under the MIT License in the root LICENSE.

The bundled sam_2-1.0-py3-none-any.whl is built from Meta's official SAM2 source,
commit 2b90b9f5ceec907a1c18123530e92e794ad901a4, with SAM2_BUILD_CUDA=0.
This wheel contains the Python backend and model configurations. It omits the optional
CUDA connected-component extension. Its SHA256 is
a1b5d867f7724c0ed823bf3c65854749cd44a4fd02f1782a709e5306fe54ae8c.
Source: https://github.com/facebookresearch/sam2
License: Apache 2.0, reproduced as SAM2_LICENSE.txt.

The vendor folder also includes pure Python iopath and ANTLR runtime wheels built
from the public PyPI source distributions. Their own license notices are retained
inside the wheels. They avoid requiring build tools during the default installation.

SAM1 source and weights come from https://github.com/facebookresearch/segment-anything
under Apache 2.0. SAM1_LICENSE.txt contains the upstream license.
SAM3 is optional and uses Meta's separate SAM license, reproduced as SAM3_LICENSE.txt.
Source: https://github.com/facebookresearch/sam3
The user obtains model weights through upstream download/access procedures.

LaMa paper/source: https://github.com/advimman/lama
The optional TorchScript checkpoint is obtained from the simple-lama-inpainting
release: https://github.com/enesmsahin/simple-lama-inpainting/releases/tag/v0.1.0
No model checkpoints are bundled in this source release.

AnyLabeling was studied as a reference for model management, checkpoint caching,
ROI prompts, GUI organization and executable packaging:
https://github.com/vietanhdev/anylabeling
No AnyLabeling implementation source is copied into this application.

X-AnyLabeling's vertex movement and nearest-point interactions were also reviewed:
https://github.com/CVHub520/X-AnyLabeling
No X-AnyLabeling source is copied into this application. The persistent contours,
deletion-radius behavior and cubic smoothing in this release are implemented here.

PySide6/Qt, PyTorch, torchvision, OpenCV, NumPy, SciPy, RosettaSciIO, tifffile,
imagecodecs, Pillow, Matplotlib and the remaining dependencies retain their own
licenses in installed distribution metadata. Redistributors should retain these
notices when distributing a native portable build.

Optional integration-test fixtures are downloaded from
https://github.com/hyperspy/rosettasciio/tree/main/rsciio/tests/data
and Meta's https://github.com/facebookresearch/segment-anything/tree/main/notebooks/images .
The release stores test results, not those external images/weights.
The bundled example image is a generated synthetic particle field, not acquired data.

## Text grounding in version 1.4

SAM2 / SAM2.1 text prompts combine the official SAM image predictor with
IDEA Research Grounding DINO Tiny through Hugging Face Transformers 4.53.3.
Grounding DINO repository: https://github.com/IDEA-Research/GroundingDINO
Model: https://huggingface.co/IDEA-Research/grounding-dino-tiny
Pinned model revision: a2bb814dd30d776dcf7e30523b00659f4f141c71
Transformers documentation: https://huggingface.co/docs/transformers/v4.53.3/en/model_doc/grounding-dino
Grounding DINO and Transformers use Apache 2.0 licensing as stated by their upstream distributions.
No detector weights are bundled in this application archive. Preserve model and
library license files when redistributing their separately downloaded artifacts.


## Version 1.4.2 restoration and calibration backends

openpyxl: https://openpyxl.readthedocs.io/ (MIT).
SPORCO: https://github.com/bwohlberg/sporco (BSD-3-Clause).
CAREamics: https://github.com/CAREamics/careamics (BSD-3-Clause).
BM3D/BM4D: https://pypi.org/project/bm3d/ and https://pypi.org/project/bm4d/ . These native backend distributions have academic/non-commercial terms. This application's MIT license does not relicense them. No backend native binaries are bundled in this source/wheel archive; the installer obtains the upstream distributions. Retain their full licenses when redistributing installed packages or portable builds.
SAM3.1 uses the official SAM3 upstream license and separately gated sam3.1_multiplex.pt weights from https://huggingface.co/facebook/sam3.1 . No SAM3/SAM3.1 weights are bundled.
