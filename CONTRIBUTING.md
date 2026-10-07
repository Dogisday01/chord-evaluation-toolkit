# Development process

Use small issues with a requirement, expected behavior and acceptance evidence. The task board stages are Backlog, In progress, Validation and Done; limit active implementation to two items. A solo contributor uses self-review and automated checks without claiming full Scrum or an independent human reviewer.

Use short feature branches, descriptive commits and pull requests for changes. Review the requirement and negative examples before accepting a change. Run lint, tests and distribution verification. Keep protected research data, environments and generated runs out of Git. Tag a tested state with a version matching pyproject.toml.

Record changes to alphabet, timing tolerance or coverage rules as protocol changes. An old result must not silently be compared with a new protocol. A passing test is useful evidence only if its expected value is independent of the function under test.
