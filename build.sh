# Created by Google Gemini
#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download Stockfish 17.1 for Ubuntu
echo "Downloading Stockfish 17.1 binary..."
# Updated link to the verified .tar version
wget https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar

# 3. Extract the tar file
echo "Extracting..."
tar -xf stockfish-ubuntu-x86-64-avx2.tar

# 4. Move and Rename to 'stockfish-binary'
# We use a wildcard to find the binary regardless of the folder name
mv stockfish/stockfish-ubuntu-x86-64-avx2 ./stockfish-binary

# 5. Clean up
rm -rf stockfish stockfish-ubuntu-x86-64-avx2.tar

# 6. Set permissions
chmod +x ./stockfish-binary
echo "Success: Stockfish binary installed at ./stockfish-binary"