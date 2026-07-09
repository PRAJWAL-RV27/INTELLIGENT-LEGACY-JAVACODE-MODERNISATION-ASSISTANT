#!/usr/bin/env python3
"""
GUI for Java 8→21 Transformer
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import shutil
import tempfile
from pathlib import Path

from file_walker import FileWalker
from java_transformer import JavaTransformer
from reporter import Reporter
from github_source import prepare_source_from_github_url

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TransformerGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Java 8→21 Transformer - Professional Edition")
        self.root.geometry("1000x900")
        self.root.resizable(True, True)
        
        # Set dark cosmic background
        self.root.configure(fg_color="#0f172a")

        # Variables
        self.source_dir = None
        self.temp_dest_dir = None
        self.github_source_url = None
        self.temp_source_dir = None
        self.is_transforming = False
        self.dest_dir_final = None
        self.summary_final = None
        self.last_dry_run = False
        self.last_output_file_count = 0

        # Create widgets
        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = ctk.CTkFrame(self.root, fg_color="#1e3a8a", corner_radius=0)
        header_frame.pack(fill="x", pady=0)
        header_label = ctk.CTkLabel(header_frame, text="🚀 Java 8→21 Transformer", font=ctk.CTkFont(size=32, weight="bold"), text_color="white")
        header_label.pack(pady=20)
        subtitle = ctk.CTkLabel(header_frame, text="Transform your Java code to modern Java 21 with ease", font=ctk.CTkFont(size=14), text_color="#bfdbfe")
        subtitle.pack(pady=(0, 20))

        # Main container with padding
        main_frame = ctk.CTkScrollableFrame(
            self.root,
            fg_color="transparent",
            scrollbar_fg_color="#0f172a",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
        )
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Theme and settings
        settings_frame = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=15, border_width=2, border_color="#3b82f6")
        settings_frame.pack(fill="x", pady=(0, 25))
        ctk.CTkLabel(settings_frame, text="⚙️ Settings", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(15, 10), padx=20, anchor="w")
        theme_inner = ctk.CTkFrame(settings_frame, fg_color="transparent")
        theme_inner.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(theme_inner, text="Appearance:", text_color="#e2e8f0").pack(side="left")
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(theme_inner, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.pack(side="right")
        self.appearance_mode_optionemenu.set("Dark")

        # Input section
        input_frame = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=15, border_width=2, border_color="#3b82f6")
        input_frame.pack(fill="x", pady=(0, 25))
        ctk.CTkLabel(input_frame, text="📁 GitHub Source Folder", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(15, 15), padx=20, anchor="w")

        # Source
        source_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        source_frame.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(source_frame, text="GitHub Folder URL:", font=ctk.CTkFont(weight="bold", size=13), text_color="#e2e8f0").pack(anchor="w", pady=(0, 8))
        self.source_entry = ctk.CTkEntry(source_frame, placeholder_text="https://github.com/owner/repo/tree/main/path/to/folder", height=45, font=ctk.CTkFont(size=12), text_color="white")
        self.source_entry.pack(fill="x", pady=(0, 10))
        self.source_btn = ctk.CTkButton(source_frame, text="📥 Load GitHub Source", command=self.select_source, fg_color="#0891b2", hover_color="#0e7490", text_color="white", font=ctk.CTkFont(size=13, weight="bold"), height=40, corner_radius=8)
        self.source_btn.pack(fill="x")

        # Options
        options_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        options_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(options_frame, text="Options:", font=ctk.CTkFont(weight="bold", size=13), text_color="#e2e8f0").pack(anchor="w", pady=(0, 10))
        switches_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        switches_frame.pack(fill="x")
        self.verbose_switch = ctk.CTkSwitch(switches_frame, text="Verbose Output", onvalue=1, offvalue=0, button_color="#64748b", button_hover_color="#475569", progress_color="#06b6d4", text_color="#e2e8f0", font=ctk.CTkFont(size=12))
        self.verbose_switch.pack(side="left", padx=(0, 30))
        self.dry_run_switch = ctk.CTkSwitch(switches_frame, text="Dry Run (Preview Only)", onvalue=1, offvalue=0, button_color="#64748b", button_hover_color="#475569", progress_color="#f59e0b", text_color="#e2e8f0", font=ctk.CTkFont(size=12))
        self.dry_run_switch.pack(side="left")

        # Transform button
        self.transform_btn = ctk.CTkButton(main_frame, text="🚀 Start Transformation", command=self.start_transformation, fg_color="#dc2626", hover_color="#b91c1c", text_color="white", font=ctk.CTkFont(size=16, weight="bold"), height=55, corner_radius=10)
        self.transform_btn.pack(fill="x", pady=(0, 25))

        # Preview section (hidden until transformation starts)
        self.preview_frame = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=15, border_width=2, border_color="#3b82f6")
        ctk.CTkLabel(self.preview_frame, text="📊 Live Transformation Preview", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(15, 10), padx=20, anchor="w")
        self.preview_hint = ctk.CTkLabel(self.preview_frame, text="The preview will appear automatically when you start the transformation.", text_color="#cbd5e1", font=ctk.CTkFont(size=13))
        self.preview_hint.pack(pady=(0, 10), padx=20, anchor="w")
        self.progress_bar = ctk.CTkProgressBar(self.preview_frame, width=800, height=25, fg_color="#404040", progress_color="#10b981", corner_radius=10)
        self.progress_bar.pack(pady=(0, 15), padx=20, fill="x")
        self.progress_bar.set(0)
        self.progress_text = ctk.CTkTextbox(
            self.preview_frame,
            wrap="word",
            font=ctk.CTkFont(size=11),
            text_color="#e2e8f0",
            fg_color="#0f172a",
            border_width=1,
            border_color="#475569",
            activate_scrollbars=True,
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color="#475569",
        )
        self.progress_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Results section (hidden until success)
        self.results_frame = ctk.CTkFrame(main_frame, fg_color="#1e293b", corner_radius=15, border_width=2, border_color="#3b82f6")
        ctk.CTkLabel(self.results_frame, text="📥 Download Results", font=ctk.CTkFont(size=20, weight="bold"), text_color="white").pack(pady=(15, 10), padx=20, anchor="w")
        buttons_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.save_zip_btn = ctk.CTkButton(
            buttons_frame,
            text="Download Transformed Folder",
            command=self.save_zip,
            state="disabled",
            fg_color="#0891b2",
            hover_color="#0e7490",
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=45,
            corner_radius=8,
            anchor="center",
        )
        self.save_zip_btn.pack(side="left", expand=True, padx=(0, 10))
        self.save_report_btn = ctk.CTkButton(
            buttons_frame,
            text="Download Transformation Report",
            command=self.save_report,
            state="disabled",
            fg_color="#d97706",
            hover_color="#b45309",
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=45,
            corner_radius=8,
            anchor="center",
        )
        self.save_report_btn.pack(side="right", expand=True, padx=(10, 0))
        self.results_frame.pack_forget()

        # Status
        self.status_label = ctk.CTkLabel(main_frame, text="Ready to transform your Java code!", text_color="#94a3b8", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(0, 20))

        # Footer
        footer_frame = ctk.CTkFrame(self.root, fg_color="#1e3a8a", corner_radius=0)
        footer_frame.pack(fill="x", pady=0)
        footer_label = ctk.CTkLabel(footer_frame, text="© 2026 Java Transformer Pro | Built with ❤️ for developers", font=ctk.CTkFont(size=12), text_color="#bfdbfe")
        footer_label.pack(pady=15)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def select_source(self):
        github_url = self.source_entry.get().strip()
        if not github_url:
            messagebox.showerror("Error", "Please enter a GitHub folder URL.")
            return

        try:
            self.github_source_url = github_url
            self.source_dir = prepare_source_from_github_url(github_url)
            self.temp_source_dir = self.source_dir
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, github_url)
            self.status_label.configure(text="✅ GitHub source folder loaded. Ready to transform.", text_color="#10b981")
        except Exception as exc:
            self.source_dir = None
            self.temp_source_dir = None
            self.github_source_url = None
            messagebox.showerror("Error", f"Failed to load GitHub source folder:\n{exc}")

    def start_transformation(self):
        if not self.source_dir:
            messagebox.showerror("Error", "Please load a GitHub source folder first.")
            return
        if not self.source_dir.exists() or not self.source_dir.is_dir():
            messagebox.showerror("Error", "The loaded source folder does not exist.")
            return

        # Create temp destination
        self.temp_dest_dir = Path(tempfile.mkdtemp(prefix="java_transform_"))
        self.dest_dir_final = None
        self.summary_final = None
        self.last_output_file_count = 0
        self.last_dry_run = bool(self.dry_run_switch.get())

        self.show_preview_section()
        self.results_frame.pack_forget()
        self.is_transforming = True
        self.transform_btn.configure(state="disabled", text="🔄 Transforming...", fg_color="#64748b")
        self.progress_text.delete("0.0", "end")
        self.progress_bar.set(0)
        self.status_label.configure(text="🚀 Starting transformation...", text_color="#06b6d4")

        # Disable inputs until complete
        self.source_btn.configure(state="disabled")
        self.save_zip_btn.configure(state="disabled")
        self.save_report_btn.configure(state="disabled")

        # Run in thread
        thread = threading.Thread(target=self.run_transformation)
        thread.start()

    def show_preview_section(self):
        if not self.preview_frame.winfo_ismapped():
            self.preview_frame.pack(fill="both", expand=True, pady=(0, 25))

    def show_results_section(self):
        if not self.results_frame.winfo_ismapped():
            self.results_frame.pack(fill="x", pady=(0, 25))

    def run_transformation(self):
        try:
            source = self.source_dir
            dest = self.temp_dest_dir
            verbose = bool(self.verbose_switch.get())
            dry_run = bool(self.dry_run_switch.get())

            self.update_progress(f"📂 Source: {source}\n📂 Temp Destination: {dest}\n🔍 Dry run: {dry_run}\n📝 Verbose: {verbose}\n\n")

            walker = FileWalker(source, dest)
            transformer = JavaTransformer(verbose=verbose)
            reporter = Reporter(verbose=verbose)

            java_files = walker.find_java_files()
            if not java_files:
                self.update_progress("❌ No .java files found in source directory.\n")
                self.finish_transformation(None, None, dry_run=dry_run)
                return

            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)

            self.update_progress(f"✅ Found {len(java_files)} Java file(s). Processing...\n\n")

            files_written = 0
            for i, java_file in enumerate(java_files, 1):
                rel_path = java_file.relative_to(source)
                dest_file = dest / rel_path

                self.update_progress(f"🔄 [{i}/{len(java_files)}] Processing {rel_path}...\n")

                try:
                    original = java_file.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    self.update_progress(f"⚠️  [WARN] Could not read {rel_path}: {e}\n")
                    continue

                transformed, changes = transformer.transform(original, str(rel_path))
                reporter.record(str(rel_path), changes)

                if not dry_run:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_text(transformed, encoding="utf-8")
                    files_written += 1
                    self.update_progress(f"   ✅ Written to {dest_file}\n")

                progress_value = i / len(java_files)
                self.progress_bar.set(progress_value)
                self.root.update_idletasks()

            if not dry_run:
                self.update_progress(f"\n📝 Successfully written {files_written} transformed file(s).\n")
                self.update_progress("📋 Copying non-Java files...\n")
                walker.copy_non_java_files()
                walker.patch_config_files(verbose=verbose)

            summary = reporter.get_summary_text(dry_run=dry_run)
            self.update_progress(f"\n📊 {summary}\n")

            self.finish_transformation(dest, summary, dry_run=dry_run)

        except Exception as e:
            self.update_progress(f"❌ Error: {str(e)}\n")
            self.finish_transformation(None, None, dry_run=False)

    def update_progress(self, text):
        self.progress_text.insert("end", text)
        self.progress_text.see("end")
        self.root.update_idletasks()

    def finish_transformation(self, dest_dir, summary, dry_run=False):
        self.is_transforming = False
        self.last_dry_run = bool(dry_run)
        self.transform_btn.configure(state="normal", text="🚀 Start Transformation", fg_color="#dc2626")
        self.source_btn.configure(state="normal")

        if dest_dir and summary:
            # Count files in destination
            if dest_dir.exists():
                file_count = sum(1 for _ in dest_dir.rglob("*") if _.is_file())
            else:
                file_count = 0

            self.last_output_file_count = file_count
            self.dest_dir_final = dest_dir
            self.summary_final = summary

            if self.last_dry_run:
                self.update_progress(
                    "\n⚠️ Dry run completed. No files were written, so folder download is disabled.\n"
                )
                self.save_zip_btn.configure(state="disabled")
                self.status_label.configure(
                    text="⚠️ Dry run completed. Disable Dry Run to download transformed files.",
                    text_color="#f59e0b",
                )
            elif file_count == 0:
                self.update_progress(f"\n⚠️ WARNING: Output directory exists but is empty! ({dest_dir})\n")
                self.save_zip_btn.configure(state="disabled")
                self.status_label.configure(
                    text="⚠️ No output files were created. Check the log and try again.",
                    text_color="#f59e0b",
                )
            else:
                self.update_progress(f"\n✅ Output directory contains {file_count} file(s) at {dest_dir}\n")
                self.save_zip_btn.configure(state="normal")
                self.status_label.configure(text="✅ Transformation completed successfully!", text_color="#10b981")

            self.save_report_btn.configure(state="normal")
            self.show_results_section()
        else:
            self.last_output_file_count = 0
            self.dest_dir_final = None
            self.summary_final = None
            self.status_label.configure(text="❌ Transformation failed or no files processed.", text_color="#ef4444")

    def save_zip(self):
        if not self.dest_dir_final:
            return

        if self.last_dry_run:
            messagebox.showwarning(
                "Dry Run Enabled",
                "This run used Dry Run mode, so no transformed files were written. "
                "Disable Dry Run and run again to download files.",
            )
            return

        if self.last_output_file_count == 0:
            messagebox.showwarning(
                "No Output Files",
                "No files are available to download for this run.",
            )
            return

        if not self.dest_dir_final.exists():
            messagebox.showerror(
                "Error",
                f"Output folder is missing: {self.dest_dir_final}",
            )
            return

        zip_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
            title="Save Transformed Folder As",
        )
        if zip_path:
            try:
                zip_target = Path(zip_path)
                if zip_target.suffix.lower() != ".zip":
                    zip_target = zip_target.with_suffix(".zip")

                base_name = str(zip_target.with_suffix(""))
                root_dir = str(self.dest_dir_final.parent)
                base_dir = self.dest_dir_final.name
                archive_path = shutil.make_archive(base_name, "zip", root_dir, base_dir)
                messagebox.showinfo("Success", f"📁 Folder saved as {archive_path}")
            except Exception as e:
                messagebox.showerror("Error", f"❌ Failed to save zip: {str(e)}")

    def save_report(self):
        if not self.summary_final:
            return
        report_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")], title="Save Report As")
        if report_path:
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(self.summary_final)
                messagebox.showinfo("Success", f"📄 Report saved as {report_path}")
            except Exception as e:
                messagebox.showerror("Error", f"❌ Failed to save report: {str(e)}")

    def run(self):
        self.root.mainloop()


def main():
    app = TransformerGUI()
    app.run()


if __name__ == "__main__":
    main()