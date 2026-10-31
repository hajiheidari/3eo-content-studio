# Project instructions
Work only in this repository. Preserve Espadna Sim and all unrelated infrastructure.
Use feature branches and PRs; never force-push. Never deploy without explicit approval
following production infrastructure inspection. No paid calls, publication, voice cloning,
or scraping around access restrictions. Never print secrets. Update DEVELOPMENT_STATUS.md
with actual test results and limitations. Use `uv sync --frozen`, `uv run pytest`, and
`uv run ruff check src tests migrations`. Use the existing isolated checkout, not a worktree.
