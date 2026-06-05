# Download and install the right wheel from https://github.com/Dao-AILab/flash-attention/releases
#
# FLASH_ATTN_VERSION="2.7.4.post1"
# DOWNLOAD_PATH="/tmp/"
DOWNLOAD_PATH="./"
FLASH_ATTN_VERSION="2.8.3"
# this method requires nvcc
# CUDA_VERSION=$(nvcc --version | grep -oP 'release \K[0-9]+')
## CUDA_VERSION=$(nvidia-smi | grep -oP 'CUDA Version: \K[0-9]+')
CUDA_VERSION='12'
PYTHON_VERSION=$(python -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')
TORCH_VERSION=$(python -c "import torch; print(f'''{torch.__version__.split('.')[0]}.{torch.__version__.split('.')[1]}''')");
FLASH_ATTN_WHEEL="flash_attn-${FLASH_ATTN_VERSION}+cu${CUDA_VERSION}torch${TORCH_VERSION}cxx11abiTRUE-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}-linux_x86_64.whl"
if [ ! -f "${DOWNLOAD_PATH}$FLASH_ATTN_WHEEL" ]; then
    wget "https://github.com/Dao-AILab/flash-attention/releases/download/v${FLASH_ATTN_VERSION}/$FLASH_ATTN_WHEEL" -nv -P ${DOWNLOAD_PATH} -N
    pip install "${DOWNLOAD_PATH}$FLASH_ATTN_WHEEL"
fi
