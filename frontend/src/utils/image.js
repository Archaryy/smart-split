const MAX_SIDE = 2000;
const SKIP_BELOW_BYTES = 1.5 * 1024 * 1024;

/**
 * Phone photos are often 5-12 MB. Shrink them before uploading so they send
 * quickly and stay under the server's size limit. Smaller, already-light images
 * are sent untouched. Falls back to the original file if anything goes wrong.
 */
export async function prepareImage(file) {
    try {
        // createImageBitmap applies the photo's EXIF rotation.
        const bitmap = await createImageBitmap(file);
        const longest = Math.max(bitmap.width, bitmap.height);

        if (file.size <= SKIP_BELOW_BYTES && longest <= MAX_SIDE) {
            bitmap.close();
            return file;
        }

        const scale = Math.min(1, MAX_SIDE / longest);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(bitmap.width * scale);
        canvas.height = Math.round(bitmap.height * scale);

        const context = canvas.getContext("2d");
        context.fillStyle = "#fff"; // transparent PNGs would otherwise turn black as JPEG
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));

        if (!blob || (scale === 1 && blob.size >= file.size)) return file;

        return new File([blob], `${file.name.replace(/\.[^.]+$/, "")}.jpg`, { type: "image/jpeg" });
    } catch {
        return file;
    }
}
