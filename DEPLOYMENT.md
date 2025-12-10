# Railway Deployment Guide

This guide covers deploying the CDR Intelligence Platform to Railway for testing.

## Prerequisites

1. **MongoDB Atlas Account** (Free tier available)
   - Sign up at https://www.mongodb.com/cloud/atlas
   - Create a free cluster
   - Get your connection string
   - Whitelist IP addresses (or use 0.0.0.0/0 for testing)

2. **GitHub Repository**
   - Push your code to GitHub
   - Railway connects directly to GitHub

3. **Railway Account**
   - Sign up at https://railway.app (free $5/month credit)

## Deployment Steps

### Step 1: Push Code to GitHub

Make sure your code is pushed to GitHub:
```bash
git add .
git commit -m "Ready for Railway deployment"
git push
```

### Step 2: Create Railway Project

1. Go to https://railway.app
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub account (if first time)
5. Select your repository

### Step 3: Add MongoDB Database

1. In your Railway project, click **"New"**
2. Select **"Database"**
3. Choose **"Add MongoDB"**
4. Railway will automatically:
   - Create a MongoDB instance
   - Set the `MONGODB_URL` environment variable
   - Configure connection settings

**Alternative**: If you prefer to use MongoDB Atlas:
- Skip this step
- Use your own MongoDB Atlas connection string in Step 4

### Step 4: Set Environment Variables

1. Click on your **web service** (not the database)
2. Go to the **"Variables"** tab
3. Add the following environment variables:

| Variable | Value | Required |
|----------|-------|----------|
| `DATABASE_NAME` | `cdr_intelligence` | No (has default) |
| `OPENCELLID_API_KEY` | Your API key | No (optional) |

**Note**: If you're using Railway's MongoDB addon, `MONGODB_URL` is automatically set. If using MongoDB Atlas, add:
- `MONGODB_URL`: Your MongoDB Atlas connection string

### Step 5: Deploy

Railway will automatically:
1. Detect the `Procfile` and `railway.json` configuration
2. Build your application
3. Deploy it

You can watch the deployment logs in real-time. Once deployed, Railway will provide you with a URL like:
```
https://your-app-name.up.railway.app
```

### Step 6: Verify Deployment

1. **Health Check**:
   - Visit `https://your-app-url/health`
   - Should return: `{"status": "healthy", "database": "connected", ...}`

2. **Frontend**:
   - Visit `https://your-app-url/`
   - Should see the CDR Intelligence Platform UI

3. **API**:
   - Visit `https://your-app-url/api/suspects`
   - Should return: `{"success": true, "suspects": []}`

## Environment Variables Reference

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `MONGODB_URL` | Yes* | MongoDB connection string | Auto-set by Railway MongoDB addon |
| `DATABASE_NAME` | No | Database name | `cdr_intelligence` |
| `PORT` | No | Server port | Auto-set by Railway |
| `OPENCELLID_API_KEY` | No | For cell tower coordinate lookup | None |

*Required if not using Railway's MongoDB addon

## Common Issues

### Issue: "MongoDB connection failed"
- **Solution**:
  - Check your `MONGODB_URL` environment variable
  - If using MongoDB Atlas, make sure IP whitelist includes `0.0.0.0/0` (for testing)
  - Verify the connection string format

### Issue: "Build failed"
- **Solution**:
  - Check the build logs in Railway
  - Ensure `requirements.txt` is in the root directory
  - Verify all dependencies are listed correctly

### Issue: "Static files not loading"
- **Solution**:
  - The frontend is served from FastAPI automatically
  - Check that `frontend/` directory is in your repository
  - Verify the directory structure is correct

### Issue: "Port already in use"
- **Solution**:
  - Railway automatically sets the `PORT` variable
  - The code uses `$PORT` from environment (already configured)
  - This shouldn't happen on Railway

## File Persistence

**Important**: On Railway, the filesystem is ephemeral. Files in `uploads/` and `exports/` will be lost when:
- The app restarts
- The app redeploys
- The service is updated

**For Testing**: This is usually fine as you can re-upload files.

**For Production**: Consider:
- Using MongoDB GridFS for file storage
- Using cloud storage (AWS S3, Google Cloud Storage, etc.)
- Using Railway's persistent volumes (paid plans)

## Auto-Deploy

Railway automatically deploys when you push to your GitHub repository:
1. Push changes to GitHub
2. Railway detects the push
3. Automatically rebuilds and redeploys
4. Your app updates with zero downtime

## Cost

- **Free Tier**: $5/month credit (enough for testing)
- **Paid Plans**: Start at $20/month for more resources

For testing purposes, the free tier is usually sufficient.

## Testing Your Deployment

1. **Upload a CDR file**:
   - Use the UI at `https://your-app-url/`
   - Or use curl:
     ```bash
     curl -X POST https://your-app-url/api/upload \
       -F "file=@sample_cdr_data.csv" \
       -F "suspect_name=test_suspect"
     ```

2. **Check suspects**:
   ```bash
   curl https://your-app-url/api/suspects
   ```

3. **Generate sample data**:
   ```bash
   curl -X POST "https://your-app-url/api/utils/generate-sample?suspect_name=test&record_count=50"
   ```

## Support

If you encounter issues:
1. Check Railway's deployment logs
2. Verify environment variables are set correctly
3. Test MongoDB connection locally first
4. Check Railway documentation: https://docs.railway.app
