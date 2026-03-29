try:
    import cv2
    # using zxingcpp instead of pyzbar
    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False


def scan_and_add_loop(add_callback):
    """Open webcam, scan barcodes continuously, call add_callback(code) on each new scan."""
    if not CV2_AVAILABLE:
        print("OpenCV / pyzbar not installed. Barcode scanning unavailable.")
        return

    cap = cv2.VideoCapture(0)
    last_code = ""
    print("📷 Auto-scanning... Press Q to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        for barcode in decode(frame):
            code = barcode.data.decode("utf-8")
            if code != last_code:
                print(f"✅ Scanned: {code}")
                last_code = code
                add_callback(code)
        cv2.imshow("Auto Scanner — Q to stop", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()