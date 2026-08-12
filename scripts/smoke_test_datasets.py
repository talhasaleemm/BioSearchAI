import sys

print("=" * 60)
print("STEP 1: Load bc5cdr bigbio_ner config (NER split)")
print("=" * 60)
try:
    from datasets import load_dataset
    ds = load_dataset(
        "bigbio/bc5cdr",
        name="bc5cdr_bigbio_kb",
        trust_remote_code=True,
    )
    print()
    print("Dataset loaded successfully:")
    print(ds)
    print()
    print("Train split size:", len(ds["train"]))
    print("Validation split size:", len(ds.get("validation", ds.get("dev", []))))
    print("Test split size:", len(ds["test"]))
    print()
    print("Sample record (train[0]):")
    sample = ds["train"][0]
    for k, v in sample.items():
        print(f"  {k}: {v}")
    print()

    # Count entity type distribution in train
    from collections import Counter
    entity_type_counter = Counter()
    for ex in ds["train"]:
        for ent in ex.get("entities", []):
            entity_type_counter[ent.get("type", "unknown")] += 1
    print("Entity type distribution (train):", dict(entity_type_counter))

except Exception as e:
    import traceback
    print(f"ERROR loading bc5cdr: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("STEP 2: Load bigbio/ncbi_disease bigbio_ner config")
print("=" * 60)
try:
    ds2 = load_dataset(
        "bigbio/ncbi_disease",
        name="ncbi_disease_bigbio_kb",
        trust_remote_code=True,
    )
    print("NCBI Dataset loaded:")
    print(ds2)
    print("Train size:", len(ds2["train"]))
    print("Sample (train[0]):")
    s2 = ds2["train"][0]
    for k, v in s2.items():
        print(f"  {k}: {v}")
except Exception as e:
    import traceback
    print(f"ERROR loading ncbi_disease: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("SMOKE TEST COMPLETE")
