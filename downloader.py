from pathlib import Path
import requests

import config


def download(url, destination, force=False):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0 and not force:
        print(f"[download] reuse {destination}")
        return destination

    tmp = Path(str(destination) + ".part")
    headers = {"User-Agent": config.USER_AGENT}
    with requests.get(url, stream=True, timeout=60, headers=headers) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0) or 0)
        done = 0
        with open(tmp, "wb") as fh:
            for chunk in response.iter_content(config.DOWNLOAD_CHUNK_SIZE):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done/1024/1024:.1f} MB / {total/1024/1024:.1f} MB ({done*100/total:.1f}%)", end="")
    print()
    tmp.replace(destination)
    return destination


def download_official_datasets(force=False):
    outputs = {}
    for name, url in config.DATASET_URLS.items():
        filename = url.rsplit("/", 1)[-1]
        print(f"[download] {url}")
        outputs[name] = download(url, config.DOWNLOAD_DIR / filename, force=force)
    return outputs
