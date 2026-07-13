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
import importlib


def _load_transformer(module_name: str, class_name: str):
    try:
        module = importlib.import_module(f"transformers.{module_name}")
        return getattr(module, class_name)
    except (ImportError, AttributeError):
        return None


TRANSFORMER_SPECS = [
    ("import_cleaner", "ImportCleanerTransformer"),
    ("wrapper_constructors", "WrapperConstructorTransformer"),
    ("deprecated_methods", "DeprecatedMethodsTransformer"),
    ("diamond_operator", "DiamondOperatorTransformer"),
    ("instanceof_pattern", "InstanceofPatternTransformer"),
    ("string_improvements", "StringImprovementsTransformer"),
    ("collections_factory", "CollectionsFactoryTransformer"),
    ("collectors_modern", "CollectorsModernTransformer"),
    ("string_format", "StringFormatTransformer"),
    ("sequenced_collections", "SequencedCollectionsTransformer"),
    ("instanceof_switch", "InstanceofSwitchTransformer"),
    ("record_pattern", "RecordPatternTransformer"),
    ("finalize_transform", "FinalizeTransformer"),
    ("drag_source_transform", "DragSourceContextTransformer"),
    ("drag_source_context_peer_transform", "DragSourceContextPeerTransformer"),
    ("add_notify_transform", "AddNotifyTransformer"),
    ("remove_notify_transform", "RemoveNotifyTransformer"),
    ("add_notify_component_peer_transform", "AddNotifyComponentPeerTransformer"),
    ("remove_notify_component_peer_transform", "RemoveNotifyComponentPeerTransformer"),
    ("jaxb_helpers_removal", "JAXBHelpersRemovalTransformer"),
    ("jaxb_util_removal", "JAXBUtilRemovalTransformer"),
    ("jaxb_bind_transform", "JAXBBindTransformer"),
    ("soap_transform", "SOAPTransformer"),
    ("jaxws_soap_handler_transform", "JAXWSSOAPHandlerTransformer"),
    ("org_omg_rmi_stub_transform", "OMGRMIStubTransformer"),
    ("org_omg_jmx_rmi_stub_transform", "OMGJMXRMIStubTransformer"),
    ("sending_context_transform", "SendingContextTransformer"),
    ("portable_server_transform", "PortableServerTransformer"),
    ("portable_server_portable_transform", "PortableServerPortableTransformer"),
    ("current_package_transform", "CurrentPackageTransformer"),
    ("poa_manager_package_transform", "POAManagerPackageTransformer"),
    ("poa_package_transform", "POAPackageTransformer"),
    ("portable_interceptor_transform", "PortableInterceptorTransformer"),
    ("servant_locator_package_transform", "ServantLocatorPackageTransformer"),
    ("cos_naming_transform", "CosNamingTransformer"),
    ("corba_transform", "CORBATransformer"),
    ("corba_2_3_portable_transform", "CORBA23PortableTransformer"),
    ("corba_2_3_transform", "CORBA23Transformer"),
    ("naming_context_ext_package_transform", "NamingContextExtPackageTransformer"),
    ("naming_context_package_transform", "NamingContextPackageTransformer"),
    ("corba_dyn_any_package_transform", "CORBADynAnyPackageTransformer"),
    ("corba_orb_package_transform", "CORBAORBPackageTransformer"),
    ("corba_type_code_package_transform", "CORBATypeCodePackageTransformer"),
    ("corba_portable_transform", "CORBAPortableTransformer"),
    ("dyn_any_factory_package_transform", "DynAnyFactoryPackageTransformer"),
    ("dyn_any_package_transform", "DynAnyPackageTransformer"),
    ("dynamic_any_transform", "DynamicAnyTransformer"),
    ("dynamic_transform", "DynamicTransformer"),
    ("codec_factory_package_transform", "CodecFactoryPackageTransformer"),
    ("codec_package_transform", "CodecPackageTransformer"),
    ("iop_transform", "IOPTransformer"),
    ("messaging_transform", "MessagingTransformer"),
    ("orb_init_info_package_transform", "ORBInitInfoPackageTransformer"),
    ("textlayout_equals_transform", "TextLayoutEqualsTransformer"),
    ("textlayout_hashcode_transform", "TextLayoutHashCodeTransformer"),
    ("component_getPeer_transform", "ComponentGetPeerTransformer"),
    ("menucomponent_getpeer_transform", "MenuComponentGetPeerTransformer"),
    ("get_mouse_info_peer_transform", "GetMouseInfoPeerTransformer"),
]


class JavaTransformer:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self._pipeline = []

        for module_name, class_name in TRANSFORMER_SPECS:
            transformer_cls = _load_transformer(module_name, class_name)
            if transformer_cls is not None:
                self._pipeline.append(transformer_cls())

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
