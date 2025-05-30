# Copyright (c) Microsoft Corporation.

# MIT License

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# https://github.com/microsoft/ADBench/blob/38cb7931303a830c3700ca36ba9520868327ac87/src/python/modules/PyTorch/PyTorchBA.py

"""
Changes Made:
- Added two functions to create a PyTorchBA object and call calculate_objective and calculate_jacobian
- Added two functions to convert BA output to JSON serializable objects
- Import a decorator to use converter functions
- Added a function to create BA input based on data provided in files
"""

import numpy as np
import torch
from gradbench import wrap
from gradbench.adbench.ba_data import BAInput
from gradbench.adbench.ba_sparse_mat import BASparseMat
from gradbench.adbench.itest import ITest
from gradbench.tools.pytorch.ba_objective import compute_reproj_err, compute_w_err
from gradbench.tools.pytorch.utils import to_torch_tensor, torch_jacobian


class PyTorchBA(ITest):
    """Test class for BA diferentiation by PyTorch."""

    def prepare(self, input):
        """Prepares calculating. This function must be run before
        any others."""

        self.p = len(input.obs)

        # we use tuple of tensors instead of multidimensional tensor
        # because torch doesn't differentiate by non-leaf tensors
        self.cams = tuple(to_torch_tensor(cam, grad_req=True) for cam in input.cams)

        self.x = tuple(to_torch_tensor(x, grad_req=True) for x in input.x)

        self.w = tuple(to_torch_tensor(w, grad_req=True) for w in input.w)

        self.obs = to_torch_tensor(input.obs, dtype=torch.int64)
        self.feats = to_torch_tensor(input.feats)

        self.reproj_error = torch.zeros(2 * self.p, dtype=torch.float64)
        self.w_err = torch.zeros(len(input.w))
        self.jacobian = BASparseMat(len(input.cams), len(input.x), self.p)

    def calculate_objective(self):
        reproj_error = torch.empty((self.p, 2), dtype=torch.float64)
        for j in range(self.p):
            reproj_error[j] = compute_reproj_err(
                self.cams[self.obs[j, 0]],
                self.x[self.obs[j, 1]],
                self.w[j],
                self.feats[j],
            )

            self.w_err[j] = compute_w_err(self.w[j])

        self.reproj_error = reproj_error.flatten()

    def calculate_jacobian(self):
        reproj_error = torch.empty((self.p, 2), dtype=torch.float64)
        # reprojection error jacobian calculation
        for j in range(self.p):
            camIdx = self.obs[j, 0]
            ptIdx = self.obs[j, 1]

            cam = self.cams[camIdx]
            x = self.x[ptIdx]
            w = self.w[j]

            reproj_error[j], J = torch_jacobian(
                compute_reproj_err, (cam, x, w), (self.feats[j],)
            )

            self.jacobian.insert_reproj_err_block(j, camIdx, ptIdx, J)

        # weight error jacobian calculation
        for j in range(self.p):
            self.w_err[j], J = torch_jacobian(compute_w_err, (self.w[j],))

            self.jacobian.insert_w_err_block(j, J)

        self.reproj_error = reproj_error.flatten()


# Convert objective output to dictionary
def objective_output(errors):
    r_err, w_err = errors
    num_r = len(r_err.tolist()) // 2
    num_w = len(w_err.tolist())
    return {
        "reproj_error": {"elements": r_err.tolist()[:2], "repeated": num_r},
        "w_err": {"element": w_err.tolist()[0], "repeated": num_w},
    }


# Convert jacobian output to dictionary
def jacobian_output(ba_mat):
    def dedup(A):
        return A[0:30] + [A[-1]]

    return {
        "rows": list(map(int, dedup(list(ba_mat.rows)))),
        "cols": list(map(int, dedup(list(ba_mat.cols)))),
        "vals": list(map(float, dedup(list(ba_mat.vals)))),
    }


# Parse JSON input and convert to BAInput
def prepare_input(input):
    n = input["n"]
    m = input["m"]
    p = input["p"]
    one_cam = input["cam"]
    one_X = input["x"]
    one_w = input["w"]
    one_feat = input["feat"]

    cams = np.tile(one_cam, (n, 1)).tolist()
    X = np.tile(one_X, (m, 1)).tolist()
    w = np.tile(one_w, p).tolist()
    feats = np.tile(one_feat, (p, 1)).tolist()

    camIdx = 0
    ptIdx = 0
    obs = []
    for i in range(p):
        obs.append((camIdx, ptIdx))
        camIdx = (camIdx + 1) % n
        ptIdx = (ptIdx + 1) % m

    py = PyTorchBA()
    py.prepare(BAInput(cams, X, w, obs, feats))
    return py


@wrap.multiple_runs(
    pre=prepare_input,
    post=objective_output,
)
def objective(py):
    py.calculate_objective()
    return py.reproj_error, py.w_err


@wrap.multiple_runs(
    pre=prepare_input,
    post=jacobian_output,
)
def jacobian(py):
    py.calculate_jacobian()
    return py.jacobian
