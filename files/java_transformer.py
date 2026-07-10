"""
java_transformer.py — Orchestrates the full transformation pipeline.

  Phase 1 — Safety (remove broken/removed APIs)
  1.  ImportCleaner          — comment out removed imports
  2.  WrapperConstructors    — new Integer(x) → Integer.valueOf(x)
  3.  DeprecatedMethods      — comment out removed method calls

  Phase 2 — Language modernisation (Java 7–16)
  4.  DiamondOperator        — new ArrayList<String>() → new ArrayList<>()
  5.  InstanceofPattern      — instanceof + cast → pattern variable
  6.  StringImprovements     — .length()==0 → .isEmpty()

  Phase 3 — Semantic API upgrades (Java 9–16)
  7.  CollectionsFactory     — Collections.emptyList() → List.of()
  8.  CollectorsModern       — .collect(Collectors.toUnmodifiableList()) → .toList()
  9.  StringFormat           — String.format("…",x) → "…".formatted(x)

  Phase 4 — True Java 21 finalized features
  10. SequencedCollections   — JEP 431  list.get(0) → list.getFirst()
  11. SwitchPattern          — JEP 441  if-else instanceof → switch
  12. RecordPatterns         — JEP 440  record deconstruction (same-file records)
"""
from transformers.import_cleaner         import ImportCleanerTransformer

from transformers.wrapper_constructors   import WrapperConstructorTransformer
from transformers.deprecated_methods     import DeprecatedMethodsTransformer
from transformers.diamond_operator       import DiamondOperatorTransformer
from transformers.instanceof_pattern     import InstanceofPatternTransformer
from transformers.string_improvements    import StringImprovementsTransformer
from transformers.collections_factory    import CollectionsFactoryTransformer
from transformers.collectors_modern      import CollectorsModernTransformer
from transformers.string_format          import StringFormatTransformer
from transformers.sequenced_collections  import SequencedCollectionsTransformer
from transformers.instanceof_switch      import InstanceofSwitchTransformer
from transformers.record_pattern         import RecordPatternTransformer
from transformers.finalize_transform     import FinalizeTransformer
from transformers.drag_source_transform  import DragSourceContextTransformer
from transformers.drag_source_context_peer_transform import DragSourceContextPeerTransformer
from transformers.add_notify_transform   import AddNotifyTransformer
from transformers.add_notify_transform   import AddNotifyTransformer
from transformers.remove_notify_transform import RemoveNotifyTransformer
from transformers.add_notify_component_peer_transform import AddNotifyComponentPeerTransformer
from transformers.remove_notify_component_peer_transform import RemoveNotifyComponentPeerTransformer
from transformers.jaxb_helpers_removal import JAXBHelpersRemovalTransformer
from transformers.jaxb_util_removal import JAXBUtilRemovalTransformer
from transformers.jaxb_bind_transform import JAXBBindTransformer
from transformers.soap_transform import SOAPTransformer
from transformers.jaxws_soap_handler_transform import JAXWSSOAPHandlerTransformer
from transformers.org_omg_rmi_stub_transform import OMGRMIStubTransformer
from transformers.org_omg_jmx_rmi_stub_transform import OMGJMXRMIStubTransformer
from transformers.sending_context_transform import SendingContextTransformer
from transformers.portable_server_transform import PortableServerTransformer
from transformers.portable_server_portable_transform import PortableServerPortableTransformer
from transformers.current_package_transform import CurrentPackageTransformer
from transformers.poa_manager_package_transform import POAManagerPackageTransformer
from transformers.poa_package_transform import POAPackageTransformer
from transformers.portable_interceptor_transform import PortableInterceptorTransformer
from transformers.servant_locator_package_transform import ServantLocatorPackageTransformer
from transformers.cos_naming_transform import CosNamingTransformer
from transformers.dyn_any_factory_package_transform import DynAnyFactoryPackageTransformer
from transformers.dyn_any_package_transform import DynAnyPackageTransformer
from transformers.dynamic_any_transform import DynamicAnyTransformer
from transformers.dynamic_transform import DynamicTransformer
from transformers.codec_factory_package_transform import CodecFactoryPackageTransformer
from transformers.codec_package_transform import CodecPackageTransformer
from transformers.iop_transform import IOPTransformer
from transformers.messaging_transform import MessagingTransformer
from transformers.orb_init_info_package_transform import ORBInitInfoPackageTransformer
from transformers.textlayout_equals_transform import TextLayoutEqualsTransformer
from transformers.textlayout_hashcode_transform import TextLayoutHashCodeTransformer
from transformers.colormodel_finalize_transformer import ColorModelFinalizeTransformer
from transformers.Indexcolormodel_finalize_transformer import IndexColorModelFinalizeTransformer
from transformers.component_getPeer_transform import ComponentGetPeerTransformer
from transformers.menucomponent_getpeer_transform import MenuComponentGetPeerTransformer
from transformers.get_mouse_info_peer_transform import GetMouseInfoPeerTransformer

class JavaTransformer:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose   = verbose
        self._pipeline = [
            # Phase 1
            ImportCleanerTransformer(),
            JAXBBindTransformer(),
            SOAPTransformer(),
            JAXWSSOAPHandlerTransformer(),
            OMGRMIStubTransformer(),
            OMGJMXRMIStubTransformer(),
            SendingContextTransformer(),
            PortableServerTransformer(),
            PortableServerPortableTransformer(),
            CurrentPackageTransformer(),
            POAManagerPackageTransformer(),
            POAPackageTransformer(),
            PortableInterceptorTransformer(),
            ServantLocatorPackageTransformer(),
            CodecFactoryPackageTransformer(),
            CodecPackageTransformer(),
            IOPTransformer(),
            MessagingTransformer(),
            ORBInitInfoPackageTransformer(),
            CosNamingTransformer(),
            DynAnyFactoryPackageTransformer(),
            DynAnyPackageTransformer(),
            DynamicAnyTransformer(),
            DynamicTransformer(),
            WrapperConstructorTransformer(),
            DeprecatedMethodsTransformer(),
            ColorModelFinalizeTransformer(),
            IndexColorModelFinalizeTransformer(),
            FinalizeTransformer(),
            DragSourceContextTransformer(),
            DragSourceContextPeerTransformer(),
            AddNotifyTransformer(),
            RemoveNotifyTransformer(),
            AddNotifyComponentPeerTransformer(), 
            RemoveNotifyComponentPeerTransformer(),
            MenuComponentGetPeerTransformer(),
            ComponentGetPeerTransformer(),
            GetMouseInfoPeerTransformer(),
            JAXBHelpersRemovalTransformer(),
            JAXBUtilRemovalTransformer(),
            TextLayoutEqualsTransformer(),
            TextLayoutHashCodeTransformer(),
            # Phase 2
            DiamondOperatorTransformer(),
            InstanceofPatternTransformer(),
            StringImprovementsTransformer(),
            # Phase 3
            CollectionsFactoryTransformer(),
            CollectorsModernTransformer(),
            StringFormatTransformer(),
            # Phase 4 — Java 21
            SequencedCollectionsTransformer(),   # JEP 431
            InstanceofSwitchTransformer(),          # JEP 441
            RecordPatternTransformer(),         # JEP 440
        ]

    def transform(self, content: str, filename: str = "") -> tuple[str, list[str]]:
        all_changes: list[str] = []
        for t in self._pipeline:
            content, changes = t.transform(content)
            if changes and self.verbose:
                label = t.__class__.__name__
                for c in changes:
                    print(f"    [{label}] {c}")
            all_changes.extend(changes)
        return content, all_changes