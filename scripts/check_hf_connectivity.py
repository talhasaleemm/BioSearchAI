"""Quick connectivity probe for HuggingFace datasets and model endpoints."""
import urllib.request
import urllib.error

CHECKS = [
    ("HF root", "https://huggingface.co"),
    ("BC5CDR (bigbio)", "https://huggingface.co/datasets/bigbio/bc5cdr"),
    ("NCBI Disease", "https://huggingface.co/datasets/ncbi_disease"),
    ("BC5CDR README", "https://huggingface.co/datasets/bigbio/bc5cdr/resolve/main/README.md"),
    ("NCBI Disease README", "https://huggingface.co/datasets/ncbi_disease/resolve/main/README.md"),
    ("BioBERT model card", "https://huggingface.co/dmis-lab/biobert-base-cased-v1.2"),
    ("BioBERT config.json", "https://huggingface.co/dmis-lab/biobert-base-cased-v1.2/resolve/main/config.json"),
    ("BioBERT pytorch_model.bin HEAD", "https://huggingface.co/dmis-lab/biobert-base-cased-v1.2/resolve/main/pytorch_model.bin"),
]

for label, url in CHECKS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "python-urllib/3.11"}, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=12)
        cl = resp.headers.get("content-length", "?")
        print(f"OK  {resp.status}  {label}  (content-length: {cl})")
    except urllib.error.HTTPError as e:
        print(f"ERR {e.code}  {label}  ({e.reason})")
    except Exception as e:
        print(f"ERR ???  {label}  ({type(e).__name__}: {e})")
