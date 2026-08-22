import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from java_transformer import JavaTransformer


def test_javax_activity_import_reports_manual_review_without_rewriting():
    content = '''
import javax.activity.ActivityRequiredException;

class Example {
    private javax.activity.ActivityRequiredException ex;
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert any("Original API: javax.activity.ActivityRequiredException" in change for change in changes)
    assert any("Replacement API: None" in change for change in changes)
    assert any("Action: MANUAL_REVIEW" in change for change in changes)


def test_javax_activity_wildcard_import_and_fully_qualified_usage_are_reported():
    content = '''
import javax.activity.*;

class Example {
    javax.activity.ActivityRequiredException field;
    void test(javax.activity.ActivityRequiredException value) {
        javax.activity.ActivityRequiredException local = value;
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert any("Original API: javax.activity.*" in change for change in changes)
    assert any("Original API: javax.activity.ActivityRequiredException" in change for change in changes)
    assert not any("jakarta.activity" in change for change in changes)


def test_javax_activity_ignores_comments_strings_and_reflection():
    content = '''
class Example {
    String text = "javax.activity.ActivityRequiredException";
    // javax.activity.ActivityRequiredException
    /* javax.activity.SomeClass */
    /** javax.activity.Other */
    void test() throws Exception {
        Class.forName("javax.activity.ActivityRequiredException");
        ClassLoader.loadClass("javax.activity.ActivityRequiredException");
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert not changes


def test_javax_activity_unrelated_packages_and_jakarta_are_ignored():
    content = '''
import javax.activation.DataHandler;
import javax.mail.Session;
import jakarta.activity.SomeClass;

class Example {
    javax.activation.DataHandler activation;
    javax.mail.Session session;
    jakarta.activity.SomeClass jakartaValue;
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.activation.DataHandler;" in transformed
    assert "import javax.mail.Session;" in transformed
    assert "import jakarta.activity.SomeClass;" in transformed
    assert not any("javax.activity" in change for change in changes)
    assert not any("jakarta.activity" in change for change in changes)


def test_javax_activity_handles_generic_array_cast_and_instanceof_cases():
    content = '''
import java.util.List;

class Example {
    List<javax.activity.SomeClass> values;
    javax.activity.SomeClass[] array;
    void test(Object value) {
        javax.activity.SomeClass x = (javax.activity.SomeClass) value;
        if (value instanceof javax.activity.SomeClass) {
            System.out.println(x);
        }
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed == content
    assert any("Original API: javax.activity.SomeClass" in change for change in changes)
    assert any("Action: MANUAL_REVIEW" in change for change in changes)
