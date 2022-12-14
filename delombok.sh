#!/bin/sh
set -eu

here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

lombokjar="${here}/lombok.jar"
if [ ! -f "$lombokjar" ]; then
  curl "https://projectlombok.org/downloads/lombok.jar" -o "$lombokjar"
fi

dir="$1"
if [ ! -d "$dir" ]; then
  echo 'Given path is not a directory!'
  exit 1
fi

find "$dir" -name "*.java" -type f | while read jf; do
  python3 "${here}/delombok.py" "$jf" "$jf"
  # Replace imports of lombok.* with lombok.NonNull, otherwise the delomboked
  # file will still be ignored by CodeQL
  sed -r -i 's/^import[[:space:]]+lombok\.\*;$/import lombok.NonNull;/g' "$jf"
  # Remove any remaining lombok imports (except NonNull)
  sed -r -i '/^.*NonNull;/! s/import[[:space:]]+lombok\..*;//g' "$jf"
  # Remove any @Generated annotations, as they would prevent CodeQL from analyzing
  # the file. This can happen if, for example, already delomboked code is stored
  # in the repository.
  sed -r -i 's/@Generated( |$)//g' "$jf"
done
