FROM julia:1.10.9
# Julia's Manifest.toml files bake in paths.
# We thus want to mirror the directory structure from the repository,
# such that we are able to update the Manifest.toml files directly.
WORKDIR /tools/reversediff-jl
RUN julia -e "import Pkg; Pkg.update()"
COPY julia/GradBench /julia/GradBench
# Copy over the minimal files needed to install all dependencies
COPY tools/reversediff-jl/Project.toml /tools/reversediff-jl/
COPY tools/reversediff-jl/Manifest.toml /tools/reversediff-jl/
RUN julia --project=. -e 'import Pkg; Pkg.instantiate()'
# Copy over the rest of the files
COPY tools/reversediff-jl /tools/reversediff-jl
ENTRYPOINT ["julia", "--project=.", "run.jl"]
LABEL org.opencontainers.image.source=https://github.com/gradbench/gradbench
