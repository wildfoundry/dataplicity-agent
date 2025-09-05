#!/bin/bash

set -euo pipefail

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    # Check if 'python' is Python 3
    PY_VER=$(python --version 2>&1)
    if [[ $PY_VER == *"Python 3"* ]]; then
        PYTHON_CMD="python"
    else
        echo "Error: Python 3 is required for building"
        exit 1
    fi
else
    echo "Error: Python 3 not found. Please install Python 3."
    exit 1
fi

# Get version
VERSION=$($PYTHON_CMD dataplicity/_version.py)
read -p "Build dataplicity agent v${VERSION} from PyPI? [y/N] " -n 1 -r
echo
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  exit 1
fi

# Check for pyenv
if ! command -v pyenv &> /dev/null; then
  echo "pyenv not found. Please install pyenv first."
  exit 1
fi

pyenvRoot=$(pyenv root)

mkdir -p bin
rm -f bin/dataplicity bin/dataplicity-py2

# Define Python versions
py3_versions=(3.7 3.9 3.10 3.11 3.12)

#######################################
# Build Python 3.x version
#######################################
echo "========================================="
echo "Building Python 3.x version"
echo "========================================="

# Prepare Python 3 build parameters
py3_params=""
for version in "${py3_versions[@]}"; do
  fullVersion=$(pyenv install --list | grep "^  $version" | tail -1 | xargs)
  echo "${version} => ${fullVersion}"
  pyenv install -s $fullVersion
  py3_params="${py3_params}--python=$pyenvRoot/versions/$fullVersion/bin/python "
done

# Set up Python 3 virtual environment
rm -rf .build-py3
$PYTHON_CMD -m venv .build-py3
source .build-py3/bin/activate

# Install pex
pip install -q pex==2.38.1

# Build Python 3 version
echo "Building ./bin/dataplicity for Python 3.x..."
python -m pex dataplicity==${VERSION} six==1.16.0 lomond==0.3.3 distro==1.6.0 --pre \
  --python-shebang='#!/usr/bin/env python3' \
  -r requirements-py3.txt \
  -o bin/dataplicity \
  -m dataplicity.app:main \
  --no-build \
  --no-compile \
  --resolve-local-platforms \
  $py3_params

chmod +x bin/dataplicity
deactivate

#######################################
# Build Python 2.7 version
#######################################
echo "========================================="
echo "Building Python 2.7 version"
echo "========================================="

# Check if Python 2.7 is available through pyenv
pyenv install -s 2.7.18 || {
  echo "Failed to install Python 2.7.18 via pyenv. Skipping Python 2.7 build."
  goto_end=true
}

if [ "$goto_end" != "true" ]; then
  python2="$pyenvRoot/versions/2.7.18/bin/python"
  pip2="$pyenvRoot/versions/2.7.18/bin/pip"

  # Ensure pip is available for Python 2.7
  if [ ! -f "$pip2" ]; then
    echo "Installing pip for Python 2.7..."
    $python2 -m ensurepip || {
      curl https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py
      $python2 get-pip.py
      rm -f get-pip.py
    }
  fi

  # Set up a clean build directory for Python 2.7
  rm -rf .build-py2
  mkdir -p .build-py2
  cd .build-py2

  # Install packages in the build directory
  echo "Installing dependencies for Python 2.7..."
  $pip2 install -q --target "$PWD" "dataplicity==${VERSION}" --pre
  $pip2 install -q --target "$PWD" -r ../requirements-py2.txt

  # Create a launcher script
  cat > ../bin/dataplicity-py2 << EOF
#!/bin/bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PY2_SITE="\${SCRIPT_DIR}/../.build-py2"
PYTHONPATH="\${PY2_SITE}" exec $python2 -m dataplicity.app "\$@"
EOF

  chmod +x ../bin/dataplicity-py2
  cd ..
fi

#######################################
# Final Report
#######################################
echo "========================================="
echo "Build Results"
echo "========================================="

# Test Python 3.x build
if [ -f bin/dataplicity ]; then
  echo "✅ Python 3.x build completed"
  echo "   To run: ./bin/dataplicity"
else
  echo "❌ Python 3.x build failed"
fi

# Test Python 2.7 build
if [ -f bin/dataplicity-py2 ]; then
  echo "✅ Python 2.7 build completed"
  echo "   To run: ./bin/dataplicity-py2"
else
  echo "❌ Python 2.7 build failed or skipped"
fi

echo "========================================="
echo "Build Complete"
echo "========================================="