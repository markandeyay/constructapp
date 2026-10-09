# Doench 2016 Rule Set 2 ("Azimuth") scorer, packaged so the Python 2 and
# scikit-learn 0.17 requirements stay inside a container and never touch the
# main environment.
#
# Why every pin is here:
#  * python:2.7 (full image, NOT -slim): biopython compiles C extensions.
#  * scikit-learn==0.17.1: the model pickles only load on this version. 0.19.2
#    fails with KeyError: 'max_depth' and 0.20.4 with "No module named
#    sklearn.cross_validation".
#  * numpy/scipy/pandas/matplotlib/biopython: the last releases that still
#    support Python 2.7 and work with that scikit-learn.
#  * azimuth is installed with --no-deps, because its unpinned biopython
#    requirement resolves to a Python 3 only release and breaks the build.
#
# Build: docker build -t construct-azimuth:2.0 docker/azimuth
FROM python:2.7

RUN pip install --no-cache-dir \
        numpy==1.16.6 \
        scipy==1.2.3 \
        scikit-learn==0.17.1 \
        pandas==0.24.2 \
        matplotlib==2.2.5 \
        biopython==1.76 \
    && pip install --no-cache-dir --no-deps azimuth==2.0

COPY score.py /app/score.py
ENTRYPOINT ["python", "/app/score.py"]
