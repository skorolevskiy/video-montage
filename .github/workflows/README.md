# GitHub Actions Build Workflow

Simple manually triggered Docker build pipeline for the video-montage project.

## Workflow

### Build Pipeline (`ci.yml`)
- **Trigger**: Manual workflow dispatch only
- **Features**:
  - Builds Docker image with caching
  - Optional push to GitHub Container Registry
  - Uses GitHub Actions cache for faster builds

## Usage

### Running the Build
1. Go to your repository on GitHub
2. Click on the "Actions" tab
3. Select "Build" from the workflows list
4. Click "Run workflow"
5. Choose whether to push the built image to the registry
6. Click "Run workflow" button

### Options
- **Push to registry**: Check this box if you want to push the built image to `ghcr.io/skorolevskiy/video-montage:latest`

## Setup

No additional setup required - just push this workflow file to your repository and you're ready to go!
