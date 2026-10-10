#!/usr/bin/env bash
# Publish one chapter version as a GitHub Release.
#   scripts/release.sh <slug> <version> <pdf> [-t "Chapter title"] [-n notes.md]
#   scripts/release.sh rna-seq 0.1.0 build/rna-seq.pdf -t "Phân tích dữ liệu RNA-seq" -n notes.md
#   scripts/release.sh rna-seq 0.2.0 build/rna-seq.pdf -n notes.md   # title reused from the previous version
#   scripts/release.sh rna-seq 0.2.0 build/rna-seq.pdf -r             # replace the PDF of an existing version
# The tag is "<slug>-v<version>", the asset is "<tag>.pdf", and the release title is the chapter title.
# Publishing triggers .github/workflows/site.yml, which rebuilds the site.
set -euo pipefail

usage() { sed -n '2,8p' "$0"; exit 1; }
[[ $# -ge 3 ]] || usage
slug=$1 version=$2 pdf=$3
shift 3
title="" notes="" replace=0
while getopts "t:n:r" opt; do
  case $opt in
    t) title=$OPTARG ;;
    n) notes=$OPTARG ;;
    r) replace=1 ;;
    *) usage ;;
  esac
done

[[ $slug =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "slug must be lowercase ASCII words joined by '-', e.g. rna-seq" >&2; exit 1; }
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must be semver, e.g. 0.1.0" >&2; exit 1; }
[[ -f $pdf ]] || { echo "no such file: $pdf" >&2; exit 1; }
[[ -z $notes || -f $notes ]] || { echo "no such file: $notes" >&2; exit 1; }

tag="$slug-v$version"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp "$pdf" "$tmp/$tag.pdf"

if (( replace )); then
  # Same version, new file: GitHub starts a fresh counter for the new asset, and the site keeps
  # the old asset's downloads in stats/downloads.csv, so the version total carries over.
  gh release view "$tag" >/dev/null || { echo "no release $tag to replace" >&2; exit 1; }
  echo "Replacing the PDF of $tag"
  gh release upload "$tag" "$tmp/$tag.pdf" --clobber
  [[ -z $notes ]] || gh release edit "$tag" --notes-file "$notes"
  [[ -z $title ]] || gh release edit "$tag" --title "$title"
  gh workflow run site.yml --ref main  # asset uploads do not fire a release event
  exit 0
fi

if [[ -z $title ]]; then
  # Reuse the title of this chapter's most recent release.
  title=$(gh release list --limit 1000 --json tagName,name,createdAt \
    --jq "[.[] | select(.tagName | test(\"^${slug}-v[0-9]+\\\\.[0-9]+\\\\.[0-9]+\$\"))] | sort_by(.createdAt) | last | .name // empty")
  [[ -n $title ]] || { echo "first release of '$slug': pass the chapter title with -t" >&2; exit 1; }
fi

args=(--title "$title")
if [[ -n $notes ]]; then args+=(--notes-file "$notes"); else args+=(--notes ""); fi
echo "Releasing $tag: $title"
gh release create "$tag" "$tmp/$tag.pdf" "${args[@]}"
