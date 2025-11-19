# Created by Google Gemini
#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

echo "Cloning Stockfish source..."
git clone --depth 1 https://github.com/official-stockfish/Stockfish.git stockfish-source

echo "Compiling Stockfish..."
cd stockfish-source/src
make -j profile-build ARCH=x86-64-avx2 COMP=gcc

echo "Copying compiled binary and cleaning up..."
cp ./stockfish ../../stockfish-binary 

cd ../.. # Back to root
rm -rf stockfish-source

chmod +x ./stockfish-binary
echo "Stockfish binary is now installed at ./stockfish-binary"