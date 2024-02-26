{
  description = "nix-patcher is a tool for patching Nix flake inputs, semi-automatically.";

  inputs.nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

  outputs = { self, nixpkgs }: 
    let
      systems = nixpkgs.legacyPackages.x86_64-linux.go.meta.platforms;
      lib = nixpkgs.lib;
    in
    {
      packages = lib.genAttrs systems (sys: 
        let 
          pkgs = nixpkgs.legacyPackages.${sys};
          selfpkgs = self.packages.${sys};
        in
        {
          # nixpkgs pr for patch2pr: https://github.com/NixOS/nixpkgs/pull/291104
          patch2pr = pkgs.callPackage ./patch2pr.nix { inherit (selfpkgs) patch2pr; };
          nix-patcher = pkgs.callPackage ./patcher.nix { inherit (selfpkgs) patch2pr; };
        });
    };
}
