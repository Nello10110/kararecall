import Foundation
import Vision
import ImageIO

// Usage: ocr EXTRACTED_DIRECTORY. All images and OCR stay local.
guard CommandLine.arguments.count == 2 else {
    fputs("usage: ocr EXTRACTED_DIRECTORY\n", stderr)
    exit(2)
}
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let manifest = try Data(contentsOf: output.appendingPathComponent("frames.json"))
var result = try JSONSerialization.jsonObject(with: manifest) as! [String: Any]
var frames = [[String: Any]]()
for var frame in result["frames"] as! [[String: Any]] {
    try autoreleasepool {
        let url = output.appendingPathComponent(frame["image"] as! String)
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["fr-FR", "en-US"]
        request.usesLanguageCorrection = false
        try VNImageRequestHandler(url: url, options: [:]).perform([request])
        frame["lines"] = (request.results ?? []).compactMap { observation -> [String: Any]? in
            guard let candidate = observation.topCandidates(1).first else { return nil }
            let b = observation.boundingBox
            return ["text": candidate.string, "confidence": candidate.confidence,
                    "box": [b.origin.x, b.origin.y, b.width, b.height]]
        }
        frames.append(frame)
    }
}
result["engine"] = "Apple Vision VNRecognizeTextRequest"
result["frames"] = frames
result["status"] = "complete"
let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
try data.write(to: output.appendingPathComponent("ocr.json"), options: .atomic)
print("OCR: \(frames.count) frames → \(output.path)")
