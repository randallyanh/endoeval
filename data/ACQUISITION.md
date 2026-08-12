# Authorised-input acquisition — internal draft

The current staging repository contains no raw render, reference, mask, dataset, checkpoint, weight, or third-party method source.

Level-B replay will be enabled only after final release refs and licence review produce an exact `expected_inputs.json` containing, for every required object:

```text
logical role
official source
exact release or repository commit
expected logical/frame identity
SHA-256
representation constraints
access and licence note
redistribution permission
```

Users of the eventual capsule must obtain restricted inputs from official sources under applicable terms. The capsule will validate supplied bytes; it will not download, authenticate, scrape, or bypass access restrictions.
