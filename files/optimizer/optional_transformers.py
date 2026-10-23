"""
optional_transformers.py

Registry of optional Java 21 transformations.

These transformations are NOT mandatory for Java 21 compilation.
They are evaluated using the performance-aware optimizer.
"""

from __future__ import annotations

from transformers.linkedlist_getfirst_transform import (
    LinkedListGetFirstTransformer,
)

from transformers.collection_empty_transform import (
    CollectionEmptyTransformer,
)

from transformers.sequenced_list_reverse_transform import (
    SequencedListReverseTransformer,
)

from transformers.sequenced_values_transform import (
    SequencedValuesTransformer,
)

from transformers.sequenced_key_set_transform import (
    SequencedKeySetTransformer,
)

from transformers.sequenced_entry_set_transform import (
    SequencedEntrySetTransformer,
)

from transformers.sequenced_map_first_entry_transform import (
    SequencedMapFirstEntryTransformer,
)

OPTIONAL_TRANSFORMERS = [
    # Existing optional transformations
    LinkedListGetFirstTransformer(),
    CollectionEmptyTransformer(),

    # New Java 21 performance-aware transformations
    SequencedListReverseTransformer(),
    SequencedValuesTransformer(),
    SequencedKeySetTransformer(),
    SequencedEntrySetTransformer(),
    SequencedMapFirstEntryTransformer()
]
