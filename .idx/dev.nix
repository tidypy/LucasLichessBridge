{ pkgs, ... }: {
  channel = "stable-23.11"; # Stable channel for reliability

  # 1. System-level packages
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.binutils  # <--- CRITICAL: PyInstaller needs this for 'objcopy' on Linux
  ];

  # 2. Environment Variables
  env = {};

  # 3. IDX Configuration
  idx = {
    # Extensions you want in VS Code
    extensions = [
      "ms-python.python"
      "tamasfe.even-better-toml"
    ];

    # 4. Automation hooks
    workspace = {
      # Runs when you create/rebuild the environment
      onCreate = {
        setup-deps = "pip install -r requirements.txt";
      };
      # Runs every time the environment starts
      onStart = {
        # Optional: You can echo a message or check versions
        check-version = "python --version";
      };
    };
  };
}