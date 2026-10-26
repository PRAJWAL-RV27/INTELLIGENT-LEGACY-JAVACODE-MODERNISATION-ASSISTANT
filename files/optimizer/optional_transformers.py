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

from transformers.string_builder_repeat_transform import (
    StringBuilderRepeatTransformer,
)

from transformers.string_indexof_range_transform import (
    StringIndexOfRangeTransformer,
)

from transformers.list_reverse_loop_transform import (
    ListReverseLoopTransformer,
)

from transformers.sequenced_reverse_iteration_transform import (
    SequencedReverseIterationTransformer,
)

from transformers.linkedhashmap_put_last_transform import (
    LinkedHashMapPutLastTransformer,
)

from transformers.sequenced_last_element_transform import (
    SequencedLastElementTransformer,
)

from transformers.string_repeat_concat_transform import (
    StringRepeatConcatTransformer,
)

from transformers.stringbuilder_compare_transform import (
    StringBuilderCompareTransformer,
)

from transformers.hexformat_transform import (
    HexFormatTransformer,
)

from transformers.read_all_bytes_transform import (
    ReadAllBytesTransformer,
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
    SequencedMapFirstEntryTransformer(),

    # More Java 21 performance-aware transformations
    StringBuilderRepeatTransformer(),
    StringIndexOfRangeTransformer(),
    ListReverseLoopTransformer(),
    SequencedReverseIterationTransformer(),
    LinkedHashMapPutLastTransformer(),

    # Newer-API performance-aware transformations (Java 9 to 21)
    SequencedLastElementTransformer(),
    StringRepeatConcatTransformer(),
    StringBuilderCompareTransformer(),
    HexFormatTransformer(),
    ReadAllBytesTransformer(),
]
