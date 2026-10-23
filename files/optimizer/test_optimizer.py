from performance_analyzer import PerformanceAnalyzer


SOURCE = """
public class TestProgram {

    public static void main(String[] args) {

        long sum = 0;

        for (long i = 0; i < 10000000L; i++) {
            sum += i;
        }

        System.out.println(sum);
    }
}
"""


analyzer = PerformanceAnalyzer(
    warmup_runs=3,
    measured_runs=5,
)

result = analyzer.benchmark(
    SOURCE,
    "TestProgram.java",
)

print("BENCHMARK RESULT")
print("================")
print(result)