from performance_analyzer import PerformanceAnalyzer
from optional_optimizer import OptionalOptimizer


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


def candidate_transform(source):
    """
    TEST ONLY.

    This deliberately changes the workload so that we can verify
    that the optimizer detects a measurable improvement.

    This is NOT a real Java modernization rule.
    """
    return source.replace(
        "10000000L",
        "1000000L",
    )


analyzer = PerformanceAnalyzer(
    warmup_runs=3,
    measured_runs=5,
)

optimizer = OptionalOptimizer(
    analyzer=analyzer,
    min_runtime_improvement_percent=5.0,
)

result = optimizer.optimize(
    source_code=SOURCE,
    candidate_name="Test Performance Candidate",
    transform=candidate_transform,
    filename="TestProgram.java",
)

print(result.summary())