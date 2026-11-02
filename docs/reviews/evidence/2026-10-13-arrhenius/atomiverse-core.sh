#!/bin/bash -l
set -euo pipefail
module load buildenv-gcc/2026.03-mpich
export OPENBLAS_ROOT="$OPENBLASDIR"
export LD_LIBRARY_PATH="$LIBRARY_PATH:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
printf 'HOST=%s\n' "$(hostname)"
printf 'HEAD=%s\n' "$(git rev-parse HEAD)"
BUILD=/home/jicli594/work/molq-acceptance-20261013/build-core
cmake -S . -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DBLA_VENDOR=OpenBLAS \
 -DATV_BUILD_CUDA=OFF -DATV_BUILD_CLI=OFF -DATV_BUILD_TESTS=ON \
 -DATV_BUILD_MD=OFF -DATV_BUILD_MC=OFF -DATV_BUILD_MINIMIZER=OFF \
 -DATV_BUILD_VIB=OFF -DATV_BUILD_PATH=OFF -DATV_BUILD_SEMIEMPIRICAL=OFF \
 -DATV_BUILD_POTENTIALS=OFF -DATV_BUILD_NEIGHBOR=OFF -DATV_BUILD_EVALUATE=OFF \
 -DATV_BUILD_ANALYSIS=OFF -DATV_BUILD_IO=OFF \
 -DFETCHCONTENT_SOURCE_DIR_XTL=/home/jicli594/work/molcrafts/Atomiverse/build/_deps/xtl-src \
 -DFETCHCONTENT_SOURCE_DIR_XTENSOR=/home/jicli594/work/molcrafts/Atomiverse/build/_deps/xtensor-src \
 -DFETCHCONTENT_SOURCE_DIR_XTENSOR-BLAS=/home/jicli594/work/molcrafts/Atomiverse/build/_deps/xtensor-blas-src \
 -DFETCHCONTENT_SOURCE_DIR_SPDLOG=/home/jicli594/work/molcrafts/Atomiverse/build/_deps/spdlog-src \
 -DFETCHCONTENT_SOURCE_DIR_XSIMD=/home/jicli594/work/molcrafts/Atomiverse/build/_deps/xsimd-src \
 -DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=/home/jicli594/work/molcrafts/Atomiverse/build-gpu-job/_deps/googletest-src
cmake --build "$BUILD" -j8 --target test_mat3 test_vec3 test_real_harmonics test_units test_cpu_box test_cpu_chunked_range
ctest --test-dir "$BUILD" --output-on-failure --no-tests=error -j2 \
 -R '^(test_mat3|test_vec3|test_real_harmonics|test_units|test_cpu_box|test_cpu_chunked_range)$'
printf 'ATOMIVERSE_ACCEPTANCE=PASS\n'
