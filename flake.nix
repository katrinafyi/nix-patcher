{
  description = "nix-patcher is a tool for patching Nix flake inputs, semi-automatically.";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = nixpkgs.legacyPackages.x86_64-linux.go.meta.platforms;
      lib = nixpkgs.lib;
    in
    {
      packages = lib.genAttrs systems (sys:
        let
          pkgs = nixpkgs.legacyPackages.${sys};
        in
        {
          default = self.packages.${sys}.nix-patcher;
          nix-patcher = pkgs.callPackage ./patcher.nix { };
        }
      );
    };
}
