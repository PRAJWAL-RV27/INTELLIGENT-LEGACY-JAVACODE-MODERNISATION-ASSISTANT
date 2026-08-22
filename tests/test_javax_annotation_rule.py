import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from java_transformer import JavaTransformer


def test_javax_annotation_imports_and_fully_qualified_usage_are_migrated():
    content = '''
import javax.annotation.PostConstruct;
import javax.annotation.Resource;

class Example {
    private javax.annotation.Resource resource;
    @javax.annotation.PostConstruct
    void init(javax.annotation.Resource r) {
        javax.annotation.Resource local = r;
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.annotation.PostConstruct;" in transformed
    assert "import jakarta.annotation.Resource;" in transformed
    assert "private jakarta.annotation.Resource resource;" in transformed
    assert "@jakarta.annotation.PostConstruct" in transformed
    assert "void init(jakarta.annotation.Resource r)" in transformed
    assert "jakarta.annotation.Resource local = r;" in transformed
    assert any("Original API: javax.annotation.PostConstruct" in change for change in changes)
    assert any("Replacement API: jakarta.annotation.PostConstruct" in change for change in changes)


def test_javax_annotation_wildcard_and_generics_arrays_casts_and_instanceof_are_migrated():
    content = '''
import java.util.List;
import javax.annotation.*;

class Example {
    List<javax.annotation.Resource> resources;
    javax.annotation.Resource[] array;
    void test(Object value) {
        javax.annotation.Resource r = (javax.annotation.Resource) value;
        if (value instanceof javax.annotation.Resource) {
            System.out.println(r);
        }
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.annotation.*;" in transformed
    assert "List<jakarta.annotation.Resource> resources;" in transformed
    assert "jakarta.annotation.Resource[] array;" in transformed
    assert "jakarta.annotation.Resource r = (jakarta.annotation.Resource) value;" in transformed
    assert "instanceof jakarta.annotation.Resource" in transformed
    assert any("Original API: javax.annotation.Resource" in change for change in changes)


def test_javax_annotation_processing_is_protected():
    content = '''
import javax.annotation.processing.Generated;
import javax.annotation.PostConstruct;

class Example {
    javax.annotation.processing.Generated generated;
    @javax.annotation.PostConstruct
    void test() {}
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import javax.annotation.processing.Generated;" in transformed
    assert "javax.annotation.processing.Generated generated;" in transformed
    assert "@jakarta.annotation.PostConstruct" in transformed
    assert not any("javax.annotation.processing.Generated" in change for change in changes)
    assert any("Original API: javax.annotation.PostConstruct" in change for change in changes)


def test_javax_annotation_ignores_comments_strings_and_text_blocks():
    content = '''
import javax.annotation.PostConstruct;

class Example {
    String text = "javax.annotation.PostConstruct";
    // javax.annotation.Resource
    /* javax.annotation.PreDestroy */
    /** javax.annotation.Generated */
    String block = """
    javax.annotation.Resource
    """;
    @PostConstruct
    void test() {}
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.annotation.PostConstruct;" in transformed
    assert "String text = \"javax.annotation.PostConstruct\";" in transformed
    assert "// javax.annotation.Resource" in transformed
    assert "/* javax.annotation.PreDestroy */" in transformed
    assert "/** javax.annotation.Generated */" in transformed
    assert "String block = \"\"\"\n    javax.annotation.Resource\n    \"\"\";" in transformed
    assert not any("javax.annotation.Resource" in change for change in changes)


def test_javax_annotation_ignores_reflection_and_already_migrated_code():
    content = '''
class Example {
    void test() throws Exception {
        Class.forName("javax.annotation.Resource");
        ClassLoader.loadClass("javax.annotation.PostConstruct");
        jakarta.annotation.Resource resource = null;
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert 'Class.forName("javax.annotation.Resource");' in transformed
    assert 'ClassLoader.loadClass("javax.annotation.PostConstruct");' in transformed
    assert "jakarta.annotation.Resource resource = null;" in transformed
    assert not changes


def test_javax_annotation_idempotent_and_duplicate_free():
    content = '''
import javax.annotation.PostConstruct;
import javax.annotation.PostConstruct;

class Example {
    @javax.annotation.PostConstruct
    void test() {}
}
'''

    transformed, changes = JavaTransformer().transform(content)
    assert "import jakarta.annotation.PostConstruct;" in transformed
    assert transformed.count("jakarta.annotation.PostConstruct") == 2
    assert changes.count("Original API: javax.annotation.PostConstruct; Replacement API: jakarta.annotation.PostConstruct; Reason: Java 8 → Java 21 package migration; Action: AUTOMATED") == 1

    transformed_again, changes_again = JavaTransformer().transform(transformed)
    assert transformed_again == transformed
    assert not changes_again


def test_javax_annotation_no_change_for_unrelated_javax_packages():
    content = '''
import javax.activation.DataHandler;
import javax.activity.ActivityRequiredException;
import javax.mail.Session;
import javax.foo.Bar;

class Example {
    javax.activation.DataHandler activation;
    javax.activity.ActivityRequiredException activity;
    javax.mail.Session mailSession;
    javax.foo.Bar foo;
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "import jakarta.activation.DataHandler;" in transformed
    assert "javax.activity.ActivityRequiredException" in transformed
    assert "javax.mail.Session" in transformed
    assert "javax.foo.Bar" in transformed
    assert not any("javax.annotation" in change for change in changes)
