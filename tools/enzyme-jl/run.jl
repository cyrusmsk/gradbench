import GradBench

include("run_det.jl")
include("run_gmm.jl")
include("run_hello.jl")
include("run_llsq.jl")
include("run_lse.jl")
include("run_lstm.jl")
include("run_ode.jl")

GradBench.main("enzyme-jl")
