
set -e

echo "Running NPM install to update dependencies"
echo `date`
npm install

echo "Building frontend"
echo `date`
npm run compile

