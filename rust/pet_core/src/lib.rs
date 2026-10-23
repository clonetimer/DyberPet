//! Opt-in native resource primitives for DyberPet.
//!
//! The existing Python implementation is authoritative by default.
//! This library has no UI, interpreter entry point, file mutations, network,
//! art assets or voice generation. Its Python ABI remains stable for >=3.9.
use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct PngHeader {
    width: u32,
    height: u32,
    bit_depth: u8,
    color_type: u8,
}

fn parse_png_header(bytes: &[u8]) -> Result<PngHeader, &'static str> {
    if bytes.len() != 33 || &bytes[..8] != b"\x89PNG\r\n\x1a\n" {
        return Err("Invalid PNG image");
    }
    if &bytes[12..16] != b"IHDR" {
        return Err("PNG IHDR missing");
    }
    let width = u32::from_be_bytes(bytes[16..20].try_into().expect("fixed-size slice"));
    let height = u32::from_be_bytes(bytes[20..24].try_into().expect("fixed-size slice"));
    if width == 0 || height == 0 || width > 8192 || height > 8192 {
        return Err("Invalid PNG dimensions");
    }
    Ok(PngHeader {
        width,
        height,
        bit_depth: bytes[24],
        color_type: bytes[25],
    })
}

#[pyfunction]
fn png_metadata(py: Python<'_>, path: &str) -> PyResult<PyObject> {
    let filename = Path::new(path)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(path);
    let mut input = File::open(path).map_err(|err| PyIOError::new_err(err.to_string()))?;
    let mut bytes = [0u8; 33];
    // Python baseline reads at most 33 bytes and rejects a shorter result.
    let count = input
        .read(&mut bytes)
        .map_err(|err| PyIOError::new_err(err.to_string()))?;
    let head = parse_png_header(&bytes[..count])
        .map_err(|err| PyValueError::new_err(format!("{err}: {filename}")))?;
    let result = PyDict::new_bound(py);
    result.set_item("width", head.width)?;
    result.set_item("height", head.height)?;
    result.set_item("bit_depth", head.bit_depth)?;
    result.set_item("color_type", head.color_type)?;
    result.set_item("rgba_compatible", matches!(head.color_type, 4 | 6))?;
    Ok(result.into_py(py))
}

fn file_sha256(path: &str) -> std::io::Result<String> {
    let mut input = BufReader::new(File::open(path)?);
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let n = input.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
    }
    let digest = hash.finalize();
    Ok(digest.iter().map(|b| format!("{b:02x}")).collect())
}

#[pyfunction]
fn sha256_file(path: &str) -> PyResult<String> {
    file_sha256(path).map_err(|err| PyIOError::new_err(err.to_string()))
}

#[pyfunction]
fn engine_version() -> &'static str {
    "0.1.0"
}

#[pymodule]
fn dyberpet_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(png_metadata, module)?)?;
    module.add_function(wrap_pyfunction!(sha256_file, module)?)?;
    module.add_function(wrap_pyfunction!(engine_version, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_png(width: u32, height: u32) -> [u8; 33] {
        let mut bytes = [0u8; 33];
        bytes[..8].copy_from_slice(b"\x89PNG\r\n\x1a\n");
        bytes[12..16].copy_from_slice(b"IHDR");
        bytes[16..20].copy_from_slice(&width.to_be_bytes());
        bytes[20..24].copy_from_slice(&height.to_be_bytes());
        bytes[24] = 8;
        bytes[25] = 6;
        bytes
    }

    #[test]
    fn parses_bounded_png_header() {
        let image = parse_png_header(&dummy_png(192, 208)).unwrap();
        assert_eq!((image.width, image.height, image.bit_depth, image.color_type), (192, 208, 8, 6));
    }

    #[test]
    fn rejects_truncated_and_oversized_images() {
        assert!(parse_png_header(&dummy_png(0, 100)).is_err());
        assert!(parse_png_header(&dummy_png(8193, 10)).is_err());
        assert!(parse_png_header(&dummy_png(12, 1)[..25]).is_err());
    }

    #[test]
    fn checks_sha256_known_vector_without_filesystem() {
        let mut hash = Sha256::new();
        hash.update(b"abc");
        let digest = hash.finalize();
        let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
        assert_eq!(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }
}
