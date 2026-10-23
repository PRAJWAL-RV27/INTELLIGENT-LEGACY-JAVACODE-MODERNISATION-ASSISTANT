import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from java_transformer import JavaTransformer


def test_javax_activation_import_and_fully_qualified_reference_replaced():
    content = '''
import javax.activation.DataHandler;
import javax.activation.DataSource;

class Example {
    private javax.activation.DataHandler handler;
    void process(javax.activation.DataSource source) {
        javax.activation.DataHandler data = new javax.activation.DataHandler(source);
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.activation.DataHandler;" in transformed
    assert "import jakarta.activation.DataSource;" in transformed
    assert "private jakarta.activation.DataHandler handler;" in transformed
    assert "void process(jakarta.activation.DataSource source)" in transformed
    assert "new jakarta.activation.DataHandler(source)" in transformed
    assert "javax.activation" not in transformed
    assert any("Original API: javax.activation.DataHandler" in change for change in changes)


def test_javax_activation_comments_and_strings_are_untouched():
    content = '''
import javax.activation.DataHandler;

class Example {
    String text = "javax.activation.DataHandler";
    // javax.activation.DataHandler
    /* javax.activation.DataSource */
    /** javax.activation.DataSource */
    String x = """
    javax.activation.DataHandler
    """;
    void test() {
        DataHandler handler = null;
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.activation.DataHandler;" in transformed
    assert "String text = \"javax.activation.DataHandler\";" in transformed
    assert "// javax.activation.DataHandler" in transformed
    assert "/* javax.activation.DataSource */" in transformed
    assert "/** javax.activation.DataSource */" in transformed
    assert "String x = \"\"\"\n    javax.activation.DataHandler\n    \"\"\";" in transformed


def test_javax_activation_static_import_and_idempotent_second_run():
    content = '''
import static javax.activation.SomeClass.SOME_FIELD;
class Example {
    void test() {
        int x = SOME_FIELD;
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)
    assert "import static jakarta.activation.SomeClass.SOME_FIELD;" in transformed
    assert any("Original API: javax.activation.SomeClass" in change for change in changes)

    transformed_again, changes_again = JavaTransformer().transform(transformed)
    assert transformed_again == transformed
    assert not changes_again


def test_javax_activation_reflection_string_is_left_unchanged():
    content = '''
class Example {
    void test() throws Exception {
        Class.forName("javax.activation.DataHandler");
        ClassLoader.loadClass("javax.activation.DataHandler");
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)
    assert 'Class.forName("javax.activation.DataHandler");' in transformed
    assert 'ClassLoader.loadClass("javax.activation.DataHandler");' in transformed
    assert not changes


def test_javax_activation_handles_generics_casts_and_instanceof():
    content = '''
import javax.activation.DataHandler;
import javax.activation.DataSource;

class Example {
    void test(List<javax.activation.DataSource> sources, Object value) {
        javax.activation.DataSource ds = (javax.activation.DataSource) value;
        if (value instanceof javax.activation.DataSource) {
            DataHandler handler = new DataHandler();
        }
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "List<jakarta.activation.DataSource>" in transformed
    assert "(jakarta.activation.DataSource) value" in transformed
    assert "instanceof jakarta.activation.DataSource" in transformed
    assert any("Original API: javax.activation.DataSource" in change for change in changes)


def test_javax_activation_does_not_touch_unrelated_javax_packages():
    content = '''
import javax.activity.ActivityRequiredException;
import javax.mail.Session;
import javax.foo.Bar;

class Example {
    javax.activity.ActivityRequiredException a;
    javax.mail.Session mailSession;
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "javax.activity.ActivityRequiredException" in transformed
    assert "javax.mail.Session" in transformed
    assert "javax.foo.Bar" in transformed
    assert any("Original API: javax.activity.ActivityRequiredException" in change for change in changes)
    assert any("Action: MANUAL_REVIEW" in change for change in changes)
