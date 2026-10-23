import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from java_transformer import JavaTransformer


def test_icc_profile_finalize_detected_when_declared_and_called():
    content = '''
import java.awt.color.ICC_Profile;

class Example {
    void test(ICC_Profile profile) throws Throwable {
        profile.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert any("Original API: java.awt.color.ICC_Profile.finalize()" in change for change in changes)
    assert any("Replacement API: None" in change for change in changes)
    assert any("Action: MANUAL_REVIEW" in change for change in changes)


def test_icc_profile_finalize_detected_with_fully_qualified_type():
    content = '''
class Example {
    void test() throws Throwable {
        java.awt.color.ICC_Profile profile = null;
        profile.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert any("Original API: java.awt.color.ICC_Profile.finalize()" in change for change in changes)
    assert any("Action: MANUAL_REVIEW" in change for change in changes)


def test_icc_profile_finalize_not_detected_for_unrelated_types():
    content = '''
class MyClass {
    void test() throws Throwable {
        SomeOtherClass obj = null;
        obj.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert not any("ICC_Profile" in change for change in changes)


def test_icc_profile_finalize_not_detected_in_comments_or_strings():
    content = '''
class Example {
    String value = "java.awt.color.ICC_Profile.finalize()";
    // java.awt.color.ICC_Profile.finalize()
    /* java.awt.color.ICC_Profile.finalize() */
    String block = """
    java.awt.color.ICC_Profile.finalize()
    """;
    void test() {}
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert not changes


def test_icc_profile_finalize_idempotent_and_no_auto_replacement():
    content = '''
import java.awt.color.ICC_Profile;

class Example {
    void test(ICC_Profile profile) throws Throwable {
        profile.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)
    assert transformed == content
    assert any("Action: MANUAL_REVIEW" in change for change in changes)

    transformed_again, changes_again = JavaTransformer().transform(transformed)
    assert transformed_again == transformed
    assert changes_again == changes
    assert len(changes_again) == 1
