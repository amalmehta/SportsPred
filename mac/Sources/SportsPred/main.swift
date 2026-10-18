// SportsPred for Mac: a native window around the SportsPred website, with Mac menus and shortcuts.
import AppKit
import WebKit

let siteURL = URL(string: (Bundle.main.object(forInfoDictionaryKey: "SPSiteURL") as? String)
    ?? "https://amalmehta.github.io/SportsPred/")!

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var lastLoad = Date.distantPast
    var titleWatch: NSKeyValueObservation?
    var cacheTried = Set<URL>()  // pages we've already tried to show from cache while offline
    let refreshAfter: TimeInterval = 15 * 60  // predictions update about hourly; refresh when coming back

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = buildMenu()

        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()  // keeps the site's settings between launches
        config.applicationNameForUserAgent = "SportsPredMac/1.0"
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.setValue(false, forKey: "drawsBackground")  // no white flash in dark mode
        // pages set their real title after loading their data, so follow the title as it changes
        titleWatch = webView.observe(\.title, options: [.new]) { [weak self] view, _ in
            let title = (view.title ?? "").replacingOccurrences(of: " · SportsPred", with: "")
            self?.window?.subtitle = (title == "SportsPred" || title == "Competition") ? "" : title
        }

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1200, height: 820),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "SportsPred"
        window.minSize = NSSize(width: 380, height: 500)
        window.contentView = webView
        window.center()
        window.setFrameAutosaveName("SportsPred Main Window")
        window.makeKeyAndOrderFront(nil)

        go(siteURL)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationDidBecomeActive(_ notification: Notification) {
        if webView != nil, Date().timeIntervalSince(lastLoad) > refreshAfter { reload(nil) }
    }

    // MARK: navigation

    func go(_ url: URL) { webView.load(URLRequest(url: url, cachePolicy: .reloadRevalidatingCacheData)) }

    func isSite(_ url: URL) -> Bool {
        url.host == siteURL.host && url.path.hasPrefix(siteURL.path) || url.scheme == "about"
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        // scripts, fonts and data the page loads are fine; leaving the site opens the browser instead
        if action.targetFrame?.isMainFrame == false || isSite(url) { return decisionHandler(.allow) }
        NSWorkspace.shared.open(url)
        decisionHandler(.cancel)
    }

    // links that open a new window (e.g. the feedback form on GitHub) go to the default browser
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if let url = webView.url, !cacheTried.contains(url) {
            lastLoad = Date()  // a real network load, not a cached copy
            cacheTried.removeAll()
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        showOffline(error)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        showOffline(error)
    }

    func showOffline(_ error: Error) {
        let err = error as NSError
        if err.code == NSURLErrorCancelled { return }
        // offline: show the last copy of this page we have, before giving up
        let failed = (err.userInfo[NSURLErrorFailingURLErrorKey] as? URL) ?? webView.url ?? siteURL
        if isSite(failed), !cacheTried.contains(failed) {
            cacheTried.insert(failed)
            webView.load(URLRequest(url: failed, cachePolicy: .returnCacheDataDontLoad))
            return
        }
        let html = """
        <!doctype html><meta charset="utf-8"><meta name="color-scheme" content="light dark">
        <style>body{font:15px -apple-system;display:grid;place-items:center;height:100vh;margin:0;color:#52514e;background:#f6f6f3}
        @media (prefers-color-scheme:dark){body{background:#121211;color:#c3c2b7}}
        div{text-align:center;max-width:420px}h1{font-size:22px;color:CanvasText}a{display:inline-block;margin-top:12px;padding:8px 16px;
        border-radius:8px;background:#2a78d6;color:#fff;text-decoration:none;font-weight:600}</style>
        <div><h1>Can't reach SportsPred</h1><p>Predictions come from the SportsPred website, so the app needs an internet
        connection. Check your connection and try again.</p><a href="\(siteURL.absoluteString)">Try again</a></div>
        """
        webView.loadHTMLString(html, baseURL: siteURL)
    }

    // MARK: actions

    func runOnPage(_ js: String) { webView.evaluateJavaScript(js, completionHandler: nil) }

    @objc func openSettings(_ sender: Any?) {
        runOnPage("(document.getElementById('open-settings') || {click(){}}).click()")
    }
    @objc func sendFeedback(_ sender: Any?) { runOnPage("(document.querySelector('.fb-tab') || {click(){}}).click()") }
    @objc func reload(_ sender: Any?) {
        if webView.url == nil || webView.url?.absoluteString == "about:blank" { go(siteURL) } else { webView.reload() }
    }
    @objc func goHome(_ sender: Any?) { go(siteURL) }
    @objc func goSoccer(_ sender: Any?) { go(siteURL.appendingPathComponent("index.html").withQuery("sport=soccer")) }
    @objc func goTennis(_ sender: Any?) { go(siteURL.appendingPathComponent("index.html").withQuery("sport=tennis")) }
    @objc func goHow(_ sender: Any?) { go(siteURL.appendingPathComponent("how.html")) }
    @objc func goBack(_ sender: Any?) { webView.goBack() }
    @objc func goForward(_ sender: Any?) { webView.goForward() }
    @objc func zoomIn(_ sender: Any?) { webView.pageZoom = min(webView.pageZoom + 0.1, 3) }
    @objc func zoomOut(_ sender: Any?) { webView.pageZoom = max(webView.pageZoom - 0.1, 0.5) }
    @objc func actualSize(_ sender: Any?) { webView.pageZoom = 1 }
    /// the page being shown, as a link someone else can open (never the offline placeholder)
    var shareableURL: URL? {
        guard let url = webView.url, url.scheme == "https", isSite(url) else { return nil }
        return url
    }
    @objc func copyLink(_ sender: Any?) {
        guard let url = shareableURL else { return NSSound.beep() }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.writeObjects([url as NSURL])
        NSPasteboard.general.setString(url.absoluteString, forType: .string)
    }
    @objc func share(_ sender: Any?) {
        guard let url = shareableURL, let view = window.contentView else { return NSSound.beep() }
        let picker = NSSharingServicePicker(items: [url])
        picker.show(relativeTo: NSRect(x: view.bounds.maxX - 60, y: view.bounds.maxY - 40, width: 1, height: 1),
                    of: view, preferredEdge: .minY)
    }
    @objc func openInBrowser(_ sender: Any?) { NSWorkspace.shared.open(shareableURL ?? siteURL) }
    @objc func openSource(_ sender: Any?) { NSWorkspace.shared.open(URL(string: "https://github.com/amalmehta/SportsPred")!) }

    // MARK: menus

    func buildMenu() -> NSMenu {
        let main = NSMenu()
        func submenu(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
            let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            let menu = NSMenu(title: title)
            items.forEach(menu.addItem)
            item.submenu = menu
            main.addItem(item)
            return menu
        }
        func item(_ title: String, _ action: Selector?, _ key: String = "",
                  _ mods: NSEvent.ModifierFlags = .command, target: AnyObject? = nil) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
            i.keyEquivalentModifierMask = mods
            i.target = target
            return i
        }
        let me = self
        _ = submenu("SportsPred", [
            item("About SportsPred", #selector(NSApplication.orderFrontStandardAboutPanel(_:))),
            .separator(),
            item("Settings…", #selector(openSettings(_:)), ",", target: me),
            .separator(),
            item("Hide SportsPred", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:))),
            .separator(),
            item("Quit SportsPred", #selector(NSApplication.terminate(_:)), "q"),
        ])
        _ = submenu("File", [
            item("Share…", #selector(share(_:)), target: me),
            item("Copy Link", #selector(copyLink(_:)), "c", [.command, .shift], target: me),
            item("Open in Browser", #selector(openInBrowser(_:)), "o", [.command, .option], target: me),
            .separator(),
            item("Close Window", #selector(NSWindow.performClose(_:)), "w"),
        ])
        _ = submenu("Edit", [
            item("Undo", Selector(("undo:")), "z"),
            item("Redo", Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
        ])
        _ = submenu("View", [
            item("Reload", #selector(reload(_:)), "r", target: me),
            .separator(),
            item("Actual Size", #selector(actualSize(_:)), "0", target: me),
            item("Zoom In", #selector(zoomIn(_:)), "+", target: me),
            item("Zoom Out", #selector(zoomOut(_:)), "-", target: me),
            .separator(),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])
        _ = submenu("Go", [
            item("Back", #selector(goBack(_:)), "[", target: me),
            item("Forward", #selector(goForward(_:)), "]", target: me),
            item("Home", #selector(goHome(_:)), "h", [.command, .shift], target: me),
            .separator(),
            item("Soccer", #selector(goSoccer(_:)), "1", target: me),
            item("Tennis", #selector(goTennis(_:)), "2", target: me),
            item("How It Works", #selector(goHow(_:)), "3", target: me),
        ])
        let windowMenu = submenu("Window", [
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Zoom", #selector(NSWindow.performZoom(_:))),
            .separator(),
            item("Bring All to Front", #selector(NSApplication.arrangeInFront(_:))),
        ])
        NSApp.windowsMenu = windowMenu
        let help = submenu("Help", [
            item("Send Feedback…", #selector(sendFeedback(_:)), target: me),
            item("How the Predictions Work", #selector(goHow(_:)), target: me),
            item("SportsPred on GitHub", #selector(openSource(_:)), target: me),
        ])
        NSApp.helpMenu = help
        return main
    }
}

extension URL {
    func withQuery(_ q: String) -> URL {
        var c = URLComponents(url: self, resolvingAgainstBaseURL: false)!
        c.query = q
        return c.url!
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
