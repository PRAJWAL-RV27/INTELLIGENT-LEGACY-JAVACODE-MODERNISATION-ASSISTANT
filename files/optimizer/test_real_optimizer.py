from optimizer.optimizer_pipeline import OptionalOptimizationPipeline


with open(
    "TestLinkedList.java",
    "r",
    encoding="utf-8",
) as file:
    source = file.read()


pipeline = OptionalOptimizationPipeline(
    min_runtime_improvement_percent=5.0,
)

result = pipeline.transform(
    source,
    "TestLinkedList.java",
)


print()
print("=" * 70)
print("OPTIONAL JAVA 21 OPTIMIZATION RESULT")
print("=" * 70)

if not result.results:
    print("No optional transformation candidates were found.")

for optimization in result.results:
    print()
    print(optimization.summary())


print()
print("=" * 70)
print("FINAL SOURCE")
print("=" * 70)
print(result.source)