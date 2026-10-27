## REMOVED Requirements

### Requirement: Cosine Similarity Inference
**Reason**: In-browser product suggestion from a photo is unused.
**Migration**: Select the product on the manual sales page.

### Requirement: Embeddings Index Loading and Caching
**Reason**: The client no longer downloads an embeddings index.
**Migration**: None. Stored rows remain on the server and are not served.

### Requirement: Fallback to Classifier
**Reason**: Neither the classifier nor the similarity path remains in the client.
**Migration**: None.

### Requirement: Suggestion Display with Similarity Scores
**Reason**: The suggestion list is removed with the recognition sales page.
**Migration**: Operators confirm the product by search on the manual sales page.
