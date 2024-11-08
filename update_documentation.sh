
VERSION="1.0.0"
OLD_DOC_VERSIONS=""

rm -r ./docs
python3 -m virtualenv venv
source venv/bin/activate

# If not in an venv, do not continue
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Not in a virtual environment. Exiting."
    exit 1
fi

export version_options="$VERSION $OLD_DOC_VERSIONS"

# generate the docs for a version function:
function generate_docs() {
    INPUT_VERSION=$1
    python3 -m pdoc -o ./docs/$INPUT_VERSION -t ./doc_template django_sockets
}

pip install -r requirements.txt
generate_docs ./
generate_docs $VERSION

for version in $OLD_DOC_VERSIONS; do
    pip install ./dist/django_sockets-$version.tar.gz
    generate_docs $version
done;

pip install -e .