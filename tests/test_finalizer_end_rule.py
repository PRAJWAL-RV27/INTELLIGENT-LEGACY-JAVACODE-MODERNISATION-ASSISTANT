import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from java_transformer import JavaTransformer


def test_deflater_finalize_replaced():
    content = '''
import java.util.zip.Deflater;

class Example {
    void test() {
        Deflater deflater = new Deflater();
        deflater.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "deflater.end();" in transformed
    assert "deflater.finalize();" not in transformed
    assert any(
        "Original API: Deflater.finalize()" in change
        and "Replacement API: Deflater.end()" in change
        and "Java finalization removal" in change
        for change in changes
    )


def test_inflater_finalize_replaced():
    content = '''
import java.util.zip.Inflater;

class Example {
    void test() {
        Inflater inflater = new Inflater();
        inflater.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "inflater.end();" in transformed
    assert "inflater.finalize();" not in transformed
    assert any(
        "Original API: Inflater.finalize()" in change
        and "Replacement API: Inflater.end()" in change
        and "Java finalization removal" in change
        for change in changes
    )


def test_unrelated_finalize_call_unchanged():
    content = '''
class Thing {
    void cleanup() {
        someOther.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "someOther.finalize();" in transformed
    assert not changes


def test_unrelated_empty_finalize_method_unchanged():
    content = '''
class SomeOtherClass {
    public void finalize() throws Throwable {
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "public void finalize() throws Throwable" in transformed
    assert "Removed empty finalize() method" not in str(changes)
    assert not changes


def test_multiple_occurrences_in_same_file():
    content = '''
import java.util.zip.Deflater;
import java.util.zip.Inflater;

class Example {
    void test() {
        Deflater deflater = new Deflater();
        Inflater inflater = new Inflater();
        deflater.finalize();
        inflater.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed.count(".end();") == 2
    assert transformed.count(".finalize();") == 0
    assert len(changes) >= 2


def test_zipfile_finalize_replaced():
    content = '''
import java.util.zip.ZipFile;

class Example {
    void test() throws Exception {
        ZipFile zipFile = new ZipFile("archive.zip");
        zipFile.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "zipFile.close();" in transformed
    assert "zipFile.finalize();" not in transformed
    assert any(
        "Original API: ZipFile.finalize()" in change
        and "Replacement API: ZipFile.close()" in change
        and "Java finalization removal" in change
        for change in changes
    )


def test_zipfile_multiple_finalize_calls():
    content = '''
import java.util.zip.ZipFile;

class Example {
    void test() throws Exception {
        ZipFile first = new ZipFile("a.zip");
        ZipFile second = new ZipFile("b.zip");
        first.finalize();
        second.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert transformed.count(".close();") == 2
    assert transformed.count(".finalize();") == 0
    assert len(changes) >= 2


def test_zipfile_unrelated_finalize_unchanged():
    content = '''
class Thing {
    void cleanup() {
        someOther.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "someOther.finalize();" in transformed
    assert not changes


def test_integration_with_pipeline():
    content = '''
class Example {
    void test() throws Exception {
        java.util.zip.Deflater deflater = new java.util.zip.Deflater();
        java.util.zip.Inflater inflater = new java.util.zip.Inflater();
        java.util.zip.ZipFile zipFile = new java.util.zip.ZipFile("archive.zip");
        deflater.finalize();
        inflater.finalize();
        zipFile.finalize();
    }
}
'''

    transformed, changes = JavaTransformer().transform(content)

    assert "deflater.end();" in transformed
    assert "inflater.end();" in transformed
    assert "zipFile.close();" in transformed
    assert len(changes) == 3
