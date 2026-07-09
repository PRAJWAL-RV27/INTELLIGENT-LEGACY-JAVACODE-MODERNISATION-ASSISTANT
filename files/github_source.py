import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse


def parse_github_folder_url(url: str) -> tuple[str, str, str | None, str]:
    parsed = urlparse(url.strip())
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Please enter a valid GitHub repository URL.")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Please enter a GitHub repository URL in the form https://github.com/owner/repo")

    owner, repo = parts[0], parts[1]

    if len(parts) >= 3 and parts[2] == "tree":
        if len(parts) < 4:
            raise ValueError("The GitHub folder URL is incomplete. Include the branch name after /tree/.")
        branch = parts[3]
        folder_path = "/".join(parts[4:]) if len(parts) > 4 else ""
        return owner, repo, branch, folder_path

    if len(parts) >= 3 and parts[2] in {"blob", "raw"}:
        raise ValueError("Please provide a GitHub folder URL, not a file URL.")

    return owner, repo, None, ""


def prepare_source_from_github_url(url: str, target_root: Path | None = None) -> Path:
    owner, repo, branch, folder_path = parse_github_folder_url(url)

    if target_root is None:
        target_root = Path(tempfile.mkdtemp(prefix="github_source_"))
    else:
        target_root.mkdir(parents=True, exist_ok=True)

    clone_dir = target_root / repo
    clone_cmd = ["git", "clone", "--depth", "1"]
    if branch:
        clone_cmd.extend(["--branch", branch])
    clone_cmd.extend([f"https://github.com/{owner}/{repo}.git", str(clone_dir)])

    try:
        subprocess.run(clone_cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Git is not installed or not available on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"Unable to clone the GitHub repository: {stderr or exc}") from exc

    source_dir = clone_dir if not folder_path else clone_dir / folder_path
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(
            f"The requested GitHub folder was not found in the repository: {folder_path or '/'}"
        )

    return source_dir
