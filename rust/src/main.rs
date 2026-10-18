//! echo-guard: system component for Echo Code (no external crates).
//!   echo-guard status [host:port]        one-shot health + RAM report
//!   echo-guard watch  [host:port] [sec]  repeat the check until Ctrl+C
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::thread::sleep;
use std::time::Duration;

/// ~1.5B parameters: ~3 GB in fp16/bf16, ~6 GB in fp32 (plus runtime overhead).
const MODEL_FP16_GB: f64 = 3.0;
const MODEL_FP32_GB: f64 = 6.0;

#[cfg(windows)]
fn available_ram_gb() -> Option<f64> {
    #[repr(C)]
    struct MemStatus {
        length: u32,
        load: u32,
        total_phys: u64,
        avail_phys: u64,
        total_page: u64,
        avail_page: u64,
        total_virt: u64,
        avail_virt: u64,
        avail_ext: u64,
    }
    extern "system" {
        fn GlobalMemoryStatusEx(buf: *mut MemStatus) -> i32;
    }
    let mut s = MemStatus {
        length: std::mem::size_of::<MemStatus>() as u32,
        load: 0, total_phys: 0, avail_phys: 0, total_page: 0,
        avail_page: 0, total_virt: 0, avail_virt: 0, avail_ext: 0,
    };
    // SAFETY: s is a properly sized, initialised MEMORYSTATUSEX-compatible struct.
    if unsafe { GlobalMemoryStatusEx(&mut s) } != 0 {
        Some(s.avail_phys as f64 / 1024.0 / 1024.0 / 1024.0)
    } else {
        None
    }
}

#[cfg(not(windows))]
fn available_ram_gb() -> Option<f64> {
    let text = fs::read_to_string("/proc/meminfo").ok()?;
    let line = text.lines().find(|l| l.starts_with("MemAvailable:"))?;
    let kb: f64 = line.split_whitespace().nth(1)?.parse().ok()?;
    Some(kb / 1024.0 / 1024.0)
}

fn health(addr: &str) -> Result<String, String> {
    let sock = addr
        .to_socket_addrs()
        .map_err(|e| e.to_string())?
        .next()
        .ok_or("bad address")?;
    let mut s = TcpStream::connect_timeout(&sock, Duration::from_secs(3)).map_err(|e| e.to_string())?;
    s.set_read_timeout(Some(Duration::from_secs(3))).ok();
    let req = format!("GET /api/health HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n", addr);
    s.write_all(req.as_bytes()).map_err(|e| e.to_string())?;
    let mut out = String::new();
    s.read_to_string(&mut out).map_err(|e| e.to_string())?;
    if !out.starts_with("HTTP/1.1 200") && !out.starts_with("HTTP/1.0 200") {
        return Err(out.lines().next().unwrap_or("no response").to_string());
    }
    Ok(out.split("\r\n\r\n").nth(1).unwrap_or("").trim().to_string())
}

fn report(addr: &str) -> bool {
    let ok = match health(addr) {
        Ok(body) => {
            println!("[ok]   server {} -> {}", addr, body);
            true
        }
        Err(e) => {
            println!("[FAIL] server {} -> {}", addr, e);
            false
        }
    };
    match available_ram_gb() {
        Some(gb) => {
            let verdict = if gb >= MODEL_FP32_GB + 1.0 {
                "enough for fp32"
            } else if gb >= MODEL_FP16_GB + 1.0 {
                "enough for fp16/bf16 only"
            } else {
                "too low for the 1.5B model (demo backend only)"
            };
            println!("[info] available RAM: {:.1} GB ({})", gb, verdict);
        }
        None => println!("[info] RAM info unavailable on this OS"),
    }
    ok
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("status");
    let addr = args.get(2).cloned().unwrap_or_else(|| "127.0.0.1:8000".to_string());
    match cmd {
        "status" => std::process::exit(if report(&addr) { 0 } else { 1 }),
        "watch" => {
            let secs: u64 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(10);
            loop {
                report(&addr);
                println!("---");
                sleep(Duration::from_secs(secs));
            }
        }
        _ => {
            eprintln!("usage: echo-guard [status|watch] [host:port] [seconds]");
            std::process::exit(2);
        }
    }
}
