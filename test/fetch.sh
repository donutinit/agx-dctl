#!/bin/sh
# Baja las fuentes de referencia: darktable (version fija) y lcms2.
set -eu
cd "$(dirname "$0")"
DT_TAG=release-5.6.2
LCMS_TAG=lcms2.19.1
mkdir -p upstream/darktable
for f in src/iop/agx.c src/common/colorspaces.c src/common/colorspaces.h \
         src/common/custom_primaries.c src/common/matrices.c \
         src/common/colorspaces_inline_conversions.h src/common/dttypes.h; do
  curl -sSfL -o "upstream/darktable/$(basename "$f")" \
    "https://raw.githubusercontent.com/darktable-org/darktable/$DT_TAG/$f"
done
if [ ! -d upstream/lcms2 ]; then
  mkdir -p upstream/lcms2
  curl -sSfL "https://codeload.github.com/mm2/Little-CMS/tar.gz/refs/tags/$LCMS_TAG" \
    | tar -xz -C upstream/lcms2 --strip-components=1
fi
echo "darktable $DT_TAG y $LCMS_TAG listos en test/upstream"
