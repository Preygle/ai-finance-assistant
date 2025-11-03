document.addEventListener('DOMContentLoaded', () => {
    const useCameraBtn = document.getElementById('use-camera-btn');
    const cameraView = document.getElementById('camera-view');
    const cameraFeed = document.getElementById('camera-feed');
    const takePhotoBtn = document.getElementById('take-photo-btn');
    const photoCanvas = document.getElementById('photo-canvas');
    const receiptInput = document.getElementById('receipt-input');
    const uploadForm = document.getElementById('upload-form');

    let stream = null;

    useCameraBtn.addEventListener('click', async () => {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
            cameraView.style.display = 'none';
            useCameraBtn.textContent = 'Use Camera';
            return;
        }

        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            cameraFeed.srcObject = stream;
            cameraView.style.display = 'block';
            useCameraBtn.textContent = 'Close Camera';
        } catch (error) {
            console.error('Error accessing camera:', error);
            alert('Could not access the camera. Please make sure you have a camera connected and have granted permission.');
        }
    });

    takePhotoBtn.addEventListener('click', () => {
        const context = photoCanvas.getContext('2d');
        photoCanvas.width = cameraFeed.videoWidth;
        photoCanvas.height = cameraFeed.videoHeight;
        context.drawImage(cameraFeed, 0, 0, photoCanvas.width, photoCanvas.height);

        photoCanvas.toBlob(blob => {
            const formData = new FormData();
            formData.append('receipt', blob, 'receipt.jpg');

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    window.location.reload();
                } else {
                    alert('Upload failed.');
                }
            })
            .catch(error => {
                console.error('Error uploading image:', error);
                alert('An error occurred during upload.');
            });
        }, 'image/jpeg');
    });
});
