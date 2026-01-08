# Created by Google Gemini
#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download pre-compiled Stockfish for Ubuntu Linux
echo "Downloading Stockfish binary..."
wget https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar.xz

# 3. Extract and move
tar -xf stockfish-ubuntu-x86-64-avx2.tar.xz
# The folder inside the tar is usually named 'stockfish'
mv stockfish/stockfish-ubuntu-x86-64-avx2 ./stockfish-binary

# 4. Clean up
rm -rf stockfish stockfish-ubuntu-x86-64-avx2.tar.xz

# 5. Ensure permissions
chmod +x ./stockfish-binary
echo "Stockfish binary is ready at ./stockfish-binary"