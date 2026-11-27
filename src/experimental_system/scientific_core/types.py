"""Array type aliases used across scientific_core."""

import numpy as np
import numpy.typing as npt

ComplexArray = npt.NDArray[np.complex128]
FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
SpinArray = npt.NDArray[np.int8]  # values in {-1, +1}
CountsArray = npt.NDArray[np.uint8]  # mono8 camera frames
