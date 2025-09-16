DEFAULT_BRANCH=main

git fetch --no-tags origin "${DEFAULT_BRANCH}"

echo "DEBUG - HEAD_SHA: $(git rev-parse HEAD)"

BASE_SHA="$(git merge-base "origin/${DEFAULT_BRANCH}" HEAD)"

CURRENT_BRANCH="$(git branch --show-current)"

if [ "$CURRENT_BRANCH" = "$DEFAULT_BRANCH" ]
then
  echo "Current branch equals default"
  COMPARE_SHA="$(git rev-parse HEAD^)"
else
  COMPARE_SHA=${BASE_SHA}
fi

echo "-------DEBUG (detector)--------"
echo "BASE_SHA: ${BASE_SHA}, HEAD=$(git rev-parse HEAD)"
echo "COMPARE_SHA: ${COMPARE_SHA}, CURRENT_BRANCH=${CURRENT_BRANCH}"
git diff --name-status "${COMPARE_SHA}..HEAD"
echo "-------------------------------"

###########################
# CHANGED_ALL shows every file different between my branch's HEAD and the merge-base with main.
# When on the default branch, it will show changes between the current and previous commit
# MATCHED_CHANGES includes all python and HTML files changed when you merge main into your branch. 
###########################
CHANGED_ALL="$(git diff --name-only --diff-filter=ACMRDT "${COMPARE_SHA}..HEAD" | tr -d '\r' | sort -u)"
MATCHED_CHANGES="$(printf '%s\n' "$CHANGED_ALL" | grep -Ei '\.(py|html)$' || true)"

echo "${CHANGED_ALL}"
echo "${MATCHED_CHANGES}"

# # multi-line output
# echo "list<<EOF" >> "$GITHUB_OUTPUT"
# printf '%s\n' "$MATCHED_CHANGES" >> "$GITHUB_OUTPUT"
# echo "EOF" >> "$GITHUB_OUTPUT"

# if [ -n "$MATCHED_CHANGES" ]
# then
#   echo "any=true" >> "$GITHUB_OUTPUT"
#   echo "Matched python and HTML files:"
#   echo "$MATCHED_CHANGES"
# else
#   echo "any=false" >> "$GITHUB_OUTPUT"
# fi
