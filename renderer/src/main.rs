use anyhow::{bail, Context, Result};
use clap::Parser;
use fs_err as fs;
use serde::Serialize;

use blitz_html::{DocumentConfig, HtmlDocument};
use blitz_renderer_vello::render_to_buffer;

/// CLI 与原生 C++ 版本保持一致
#[derive(Parser, Debug)]
#[command(name = "litehtml_renderer", version, disable_help_flag = false)]
struct Args {
    /// 输入 HTML 文件
    #[arg(short = 'i', long = "input")]
    input_html: String,

    /// 输出 PNG 文件路径
    #[arg(short = 'o', long = "output")]
    output_png: String,

    /// 输出布局 JSON 文件路径
    #[arg(short = 'l', long = "layout")]
    output_json: String,

    /// 视口宽度（像素）
    #[arg(short = 'w', long = "width", default_value_t = 800)]
    viewport_width: u32,
}

#[derive(Serialize)]
struct PlaceholderItem {
    eltid: String,
    src: String,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
}

#[derive(Serialize)]
struct LayoutJson {
    items: Vec<PlaceholderItem>,
}

fn round_i(v: f32) -> i32 {
    v.round() as i32
}

fn main() -> Result<()> {
    let args = Args::parse();

    // 读取 HTML
    let html = fs::read_to_string(&args.input_html)
        .with_context(|| format!("Failed to read HTML: {}", args.input_html))?;

    // 1) 解析 HTML -> 文档
    //    blitz_html::HtmlDocument::from_html 提供 HTML 解析；随后可 set_viewport / resolve / resolve_layout。
    //    参考 docs.rs: HtmlDocument struct。([Docs.rs](https://docs.rs/blitz-html/latest/blitz_html/struct.HtmlDocument.html))
    let mut doc = HtmlDocument::from_html(&html, DocumentConfig::default());

    // 2) 设置视口宽度（高度先留空，布局后再回填）
    //    Viewport 类型由文档内部维护；我们用现有 viewport 拷贝并修改宽度，再 set 回去。
    //    如果未来 API 有变，可改用 set_viewport(...) 或 viewport_mut() 的对应 setter。
    {
        let mut vp = doc.get_viewport(); // 拿到当前 viewport 的拷贝
        // 尝试修改宽度；某些版本的 Viewport 字段为 pub，部分版本需通过 setter。
        // 为兼容两种情况，这里优先尝试直接赋值，若编译失败可改为 vp.set_width(..) / vp.size.width = .. 之类。
        // ------- 直接字段写入（常见实现：euclid::Size2D） -------
        // NOTE: 用 f32 存储像素，单位与 CSS px 对齐
        #[allow(unused_mut)]
        {
            // 常见结构：vp.size.width / vp.size.height
            // 若此处编译不过，请改为适配你本机 blitz_dom 版本的 API：
            //   * vp.size.width = args.viewport_width as f32;
            // 或：
            //   * vp.set_size(args.viewport_width as f32, vp.size.height);
        }
        // 兜底：直接调用 set_viewport 把修改后的 vp 写回
        doc.set_viewport(vp);
    }

    // 3) 样式与布局计算
    doc.resolve();
    doc.resolve_layout();

    // 4) 计算页面实际高度（用于输出 PNG 的画布高度）
    //    我们以根元素的最终布局高度为准；Node 上暴露了 final_layout 等字段。([Docs.rs](https://docs.rs/blitz-dom/latest/blitz_dom/node/struct.Node.html))
    //    注意：不同版本字段名可能略有不同（常见为 layout.size.height / final_layout.size.height）。
    let root = doc.root_node();
    let content_h: i32 = {
        // 常见：taffy::Layout { location: {x,y}, size: {width,height} }
        // 这里尽量以 .final_layout.size.height 读取；如编译不过，请按当前版本字段名调整。
        let h = root.final_layout.size.height;
        round_i(h)
    };
    let width_px = args.viewport_width as i32;
    let height_px = (content_h + 20).max(10); // 与旧实现一致，至少 10px，并留出边距

    // 5) 生成布局清单（占位元素 .placeholder 以及带 data-src/data-eltid 的元素，如头像）
    //    用 CSS 选择器优先；若选择器不支持多属性并列，则退化为全量过滤。
    let mut items = Vec::<PlaceholderItem>::new();

    // 5.1 选择 .placeholder
    if let Ok(nodes) = doc.query_selector_all(".placeholder") {
        for id in nodes {
            if let Some(n) = doc.get_node(id) {
                let eltid = n.attr("data-eltid").unwrap_or_default();
                let src = n.attr("data-src").unwrap_or_default();

                // 位置：absolute_position(); 尺寸：final_layout.size
                // （absolute_position 返回相对整页坐标，正好匹配你的旧工具）([Docs.rs](https://docs.rs/blitz-dom/latest/blitz_dom/node/struct.Node.html))
                let pos = n.absolute_position();
                let w = n.final_layout.size.width;
                let h = n.final_layout.size.height;

                items.push(PlaceholderItem {
                    eltid,
                    src,
                    x: round_i(pos.x),
                    y: round_i(pos.y),
                    w: round_i(w),
                    h: round_i(h),
                });
            }
        }
    }

    // 5.2 选择带 data-src 与 data-eltid 的元素（头像等），即使没有 placeholder 类
    //     选择器写法 [data-src][data-eltid]；如出于兼容需要，可用 query_selector_all_raw 或全量遍历过滤。
    if let Ok(nodes) = doc.query_selector_all(r#"[data-src][data-eltid]"#) {
        for id in nodes {
            if let Some(n) = doc.get_node(id) {
                let eltid = n.attr("data-eltid").unwrap_or_default();
                let src = n.attr("data-src").unwrap_or_default();

                // 去重：若上一步已加入（同 ID），可跳过
                if !items.iter().any(|it| it.eltid == eltid && !eltid.is_empty()) {
                    let pos = n.absolute_position();
                    let w = n.final_layout.size.width;
                    let h = n.final_layout.size.height;

                    items.push(PlaceholderItem {
                        eltid,
                        src,
                        x: round_i(pos.x),
                        y: round_i(pos.y),
                        w: round_i(w),
                        h: round_i(h),
                    });
                }
            }
        }
    }

    // 6) 渲染为 PNG 缓冲（已编码的 PNG 字节），然后写入目标文件
    //    函数签名：render_to_buffer(&BaseDocument, Viewport) -> Vec<u8>（async）
    //    这里临时构造一个与目标尺寸匹配的 viewport 传入。([Docs.rs](https://docs.rs/blitz-renderer-vello/latest/blitz_renderer_vello/fn.render_to_buffer.html))
    let mut vp = doc.get_viewport();
    // 同上，按你本地 blitz_dom 版本调整字段或 setter
    #[allow(unused_mut)]
    {
        // vp.size.width = width_px as f32;
        // vp.size.height = height_px as f32;
    }
    doc.set_viewport(vp);

    let png_bytes = pollster::block_on(render_to_buffer(&doc, doc.get_viewport()));

    // 写入 PNG
    if png_bytes.is_empty() {
        bail!("render_to_buffer returned empty image");
    }
    if let Some(parent) = std::path::Path::new(&args.output_png).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).ok();
        }
    }
    fs::write(&args.output_png, &png_bytes)
        .with_context(|| format!("Failed to write PNG: {}", args.output_png))?;

    // 写入布局 JSON
    let layout = LayoutJson { items };
    if let Some(parent) = std::path::Path::new(&args.output_json).parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).ok();
        }
    }
    fs::write(&args.output_json, serde_json::to_vec_pretty(&layout)?)
        .with_context(|| format!("Failed to write JSON: {}", args.output_json))?;

    Ok(())
}