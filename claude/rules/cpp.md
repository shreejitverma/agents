---
paths:
  - "**/*.{cpp,cc,cxx,c++,h,hh,hpp,hxx,ipp,tpp,inl}"
  - "**/CMakeLists.txt"
  - "**/*.cmake"
  - "**/CMakePresets.json"
---

# C++ files

- Load the `cpp-coding-standards` skill before writing or reviewing C++, and `cpp-testing` before touching tests; decide first whether the code is on a hot path, because the rules differ.
- Build the way the repo does: `cmake --preset <name>` when `CMakePresets.json` exists, otherwise `cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON && cmake --build build -j`.
- Before calling C++ work done: a clean build with the repo's warning flags, `ctest --test-dir build --output-on-failure`, `run-clang-tidy -p build` on changed files when the repo has a `.clang-tidy`, and an ASan+UBSan run (TSan for concurrent code) for anything touching memory or threads.
- Apple clang on this Mac has no MSan, no LeakSanitizer, and no libFuzzer; use Homebrew LLVM (`$(brew --prefix llvm)/bin/clang++`) for those, or say they were not run.
- Performance claims go through the `perf-loop` skill: Release build, repeated runs, percentiles, never a Debug or sanitizer build.
- Delegate a fresh-context review to the `cpp-reviewer` subagent, and a failing build to `cpp-build-resolver`.
