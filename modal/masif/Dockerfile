FROM pablogainza/masif:latest

# Stash MaSIF's own interpreter (Python 3.6, pinned by PyMesh) under /masifbin
# BEFORE we put a modern Python on the default paths. MaSIF's shell scripts
# call bare `python`, so they get 3.6 back by prepending /masifbin to PATH.
RUN mkdir -p /masifbin \
 && P=$(readlink -f $(command -v python3 || command -v python)) \
 && echo "$P" > /masif_py.txt \
 && ln -sf "$P" /masifbin/python \
 && ln -sf "$P" /masifbin/python3

# Modal's runtime needs Python >=3.9 in the image. Miniconda installs cleanly
# on this old base (glibc 2.17+) where deadsnakes/static builds may not.
RUN (command -v curl >/dev/null || (apt-get update && apt-get install -y curl)) ; \
    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-py39_4.12.0-Linux-x86_64.sh -o /tmp/mc.sh \
 && bash /tmp/mc.sh -b -p /opt/conda \
 && rm -f /tmp/mc.sh \
 && /opt/conda/bin/conda install -y -q python=3.11 \
 && /opt/conda/bin/python -m pip install --no-cache-dir --upgrade pip

# Modern Python becomes the default; MaSIF keeps 3.6 via /masifbin.
RUN rm -f /usr/local/bin/python /usr/local/bin/python3 \
 && ln -sf /opt/conda/bin/python /usr/local/bin/python3 \
 && ln -sf /opt/conda/bin/python /usr/local/bin/python
ENV PATH=/opt/conda/bin:$PATH

# The image ships /usr/local/bin/reduce as a 32-bit i386 binary on an x86_64
# base, so every protonation call dies with "Exec format error", no surface .ply
# is written, and the pipeline fails downstream in PyMesh. Everything else in
# the image (MSMS 2.6.1, APBS, PyMesh, TF 1.12) is fine. Rebuild reduce natively.
# The system cmake is 3.7.2 and upstream needs >=3.10, so use conda's cmake.
RUN /opt/conda/bin/conda install -y -q cmake \
 && git clone --depth 1 https://github.com/rlabduke/reduce.git /src/reduce \
 && mkdir -p /src/reduce/build && cd /src/reduce/build \
 && /opt/conda/bin/cmake -DCMAKE_BUILD_TYPE=Release .. \
 && make -j4 \
 && cp -f /src/reduce/build/reduce_src/reduce /usr/local/bin/reduce \
 && cp -f /src/reduce/reduce_wwPDB_het_dict.txt /usr/local/reduce_wwPDB_het_dict.txt
ENV REDUCE_HET_DICT=/usr/local/reduce_wwPDB_het_dict.txt
# Fail the build loudly if reduce still cannot execute (no pipe: a pipeline
# would return head's status and mask exactly the error we are fixing).
RUN /usr/local/bin/reduce -version > /tmp/rv 2>&1; grep -qi "reduce" /tmp/rv || (cat /tmp/rv; exit 1)
