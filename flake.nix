{
    description = "TODO";

    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
        utils.url = "github:numtide/flake-utils";
    };

    outputs = { self, nixpkgs, utils}:
        utils.lib.eachDefaultSystem (system:
            let
                pkgs = import nixpkgs {inherit system; };
                runtimeDeps = with pkgs; [
                    stdenv.cc.cc.lib
                ];
            in
            {
                devShells.default = pkgs.mkShell {
                    buildInputs = with pkgs; [
                        python312
                        uv
                        playwright-driver.browsers
                    ];
                    shellHook =  with pkgs;''
                        export UV_PYTHON_PREFERENCE=only-system
                        if [ ! -d ".venv" ]; then
                            uv venv
                        fi
                        source .venv/bin/activate

                        uv sync

                        export PLAYWRIGHT_BROWSERS_PATH=${playwright-driver.browsers}
                        export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
                        export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="ubuntu-24.04"

                        export LD_LIBRARY_PATH="${stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"

                        echo "Development environment is ready!"
                    '';
                };
            }
        );
}