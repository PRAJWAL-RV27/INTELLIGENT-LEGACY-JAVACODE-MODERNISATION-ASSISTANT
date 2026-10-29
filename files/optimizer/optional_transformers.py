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

from transformers.collection_empty_transform import (
    CollectionEmptyTransformer,
)
from transformers.sequential_stream_foreach_transform import (
    SequentialStreamForEachTransformer,
)
from transformers.string_replaceall_transform import (
    StringReplaceAllTransformer,
)

from transformers.string_matches_equals_transform import (
    StringMatchesEqualsTransformer,
)

from transformers.collections_sort_transform import (
    CollectionsSortTransformer,
)
from transformers.stringbuilder_append_valueof_transform import (
    StringBuilderAppendValueOfTransformer,
)

from transformers.arraycopy_transform import ArrayCopyTransformer
from transformers.array_mismatch_transform import ArraysMismatchTransformer
from transformers.files_mismatch_transform import FilesMismatchTransformer
from transformers.stream_transfer_transform import StreamTransferTransformer
from transformers.bytearray_write_to_transform import ByteArrayWriteToTransformer
from transformers.map_get_or_default_transform import MapGetOrDefaultTransformer
from transformers.remove_if_transform import RemoveIfTransformer
from transformers.collection_add_all_transform import CollectionAddAllTransformer
from transformers.string_builder_loop_transform import StringBuilderLoopTransformer
from transformers.path_of_transform import PathOfTransformer
from transformers.optional_is_empty_transform import OptionalIsEmptyTransformer
from transformers.string_formatted_transform import StringFormattedTransformer
from transformers.files_read_string_transform import FilesReadStringTransformer
from transformers.stringbuilder_is_empty_transform import StringBuilderIsEmptyTransformer
from transformers.strictmath_tau_transform import (
    StrictMathTauTransformer,
)

from transformers.math_abs_exact_transform import (
    MathAbsExactTransformer,
)

from transformers.math_ceil_div_transform import (
    MathCeilDivTransformer,
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

    SequentialStreamForEachTransformer(),
    StringReplaceAllTransformer(),
    StringMatchesEqualsTransformer(),
    CollectionsSortTransformer(),
    StringBuilderAppendValueOfTransformer(),

    # Additional performance-aware transformations
    ArrayCopyTransformer(),
    ArraysMismatchTransformer(),
    FilesMismatchTransformer(),
    StreamTransferTransformer(),
    ByteArrayWriteToTransformer(),
    MapGetOrDefaultTransformer(),
    RemoveIfTransformer(),
    CollectionAddAllTransformer(),
    StringBuilderLoopTransformer(),
    PathOfTransformer(),
    OptionalIsEmptyTransformer(),
    StringFormattedTransformer(),
    FilesReadStringTransformer(),
    StringBuilderIsEmptyTransformer(),

    StrictMathTauTransformer(),
    MathAbsExactTransformer(),
    MathCeilDivTransformer(),
]
